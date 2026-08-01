from __future__ import annotations

import logging

from config import Settings
from email_classifier import LLMEmailClassifier, ResponseAgent
from email_reader import EmailReader, EmailSender
from memory import MemoryStore
from models import ActionLog, AgentDecision, CycleSummary, EmailAction, EmailCategory, EmailMessage
from sample_emails import load_sample_emails
from storage import EmailDatabase
from tools import CalendarTool, NotesTool, NotificationTool, RateLimiter, VoiceNotificationTool


logger = logging.getLogger(__name__)


class DecisionAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decide(self, classification) -> AgentDecision:
        actions = [EmailAction.SAVE]
        category = classification.category.value

        if classification.category == EmailCategory.SPAM:
            actions.append(EmailAction.MARK_SPAM)
            return AgentDecision(actions=actions, requires_confirmation=False, reason="Spam is never auto-replied to.")

        if classification.needs_reply and category in self.settings.auto_reply_categories:
            actions.append(EmailAction.REPLY)

        if category in self.settings.forward_categories or classification.priority_score >= 9:
            actions.extend([EmailAction.FORWARD, EmailAction.NOTIFY])

        if classification.needs_scheduling:
            actions.append(EmailAction.SCHEDULE_MEETING)

        if classification.category in {EmailCategory.URGENT, EmailCategory.IMPORTANT}:
            actions.append(EmailAction.NOTIFY)

        requires_confirmation = (
            self.settings.require_confirmation
            and (
                EmailAction.REPLY in actions
                or EmailAction.FORWARD in actions
                or classification.risk_level == "high"
                or classification.priority_score >= 8
            )
        )
        return AgentDecision(actions=list(dict.fromkeys(actions)), requires_confirmation=requires_confirmation, reason="Policy matched.")


class EmailAutomationAgent:
    def __init__(self, settings: Settings, test_mode: bool = False) -> None:
        self.settings = settings
        self.test_mode = test_mode
        self.reader = EmailReader(
            email_address=settings.email_address,
            password=settings.email_password,
            imap_host=settings.imap_host,
            imap_port=settings.imap_port,
            attachment_dir=settings.attachment_dir,
        )
        self.sender = EmailSender(
            email_address=settings.email_address,
            password=settings.email_password,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            dry_run=settings.dry_run,
        )
        self.classifier = LLMEmailClassifier(settings)
        self.response_agent = ResponseAgent(settings)
        self.decision_agent = DecisionAgent(settings)
        self.memory = MemoryStore(settings)
        self.db = EmailDatabase(settings.database_path)
        self.rate_limiter = RateLimiter(settings.rate_limit_actions_per_minute)
        self.notifier = NotificationTool(settings)
        self.notes = NotesTool()
        self.calendar = CalendarTool()
        self.voice = VoiceNotificationTool()

    def run_once(self) -> CycleSummary:
        summary = CycleSummary()
        messages = self._observe()
        for message in messages:
            summary.processed += 1
            try:
                classification = self.classifier.classify(message)
                decision = self.decision_agent.decide(classification)
                self.db.save_email(message, classification)

                if decision.requires_confirmation:
                    self._log(message, "confirmation_required", "pending", decision.reason)
                    summary.pending_confirmation += 1
                    safe_actions = [action for action in decision.actions if action in {EmailAction.SAVE, EmailAction.NOTIFY, EmailAction.SCHEDULE_MEETING}]
                    self._act(message, classification, safe_actions, summary)
                else:
                    self._act(message, classification, decision.actions, summary)

                action_summary = ", ".join(action.value for action in decision.actions)
                self.memory.add_interaction(message, classification, action_summary)
            except Exception as exc:
                logger.exception("Error processing email %s", message.uid)
                summary.errors.append(f"{message.subject}: {exc}")
        return summary

    def _observe(self) -> list[EmailMessage]:
        logger.info("Observing unread emails")
        if self.test_mode:
            return load_sample_emails()[: self.settings.max_emails_per_cycle]
        return self.reader.fetch_unread(limit=self.settings.max_emails_per_cycle)

    def _act(
        self,
        message: EmailMessage,
        classification,
        actions: list[EmailAction],
        summary: CycleSummary,
    ) -> None:
        for action in actions:
            if not self.rate_limiter.allow():
                self._log(message, action.value, "rate_limited", "Action skipped by rate limiter.")
                summary.skipped += 1
                continue

            if action == EmailAction.SAVE:
                note_path = self.notes.save_note(
                    message,
                    f"# {message.subject}\n\nFrom: {message.sender}\n\n{message.body}\n",
                )
                self._log(message, action.value, "ok", f"Saved note to {note_path}")
                summary.actions_taken += 1
            elif action == EmailAction.REPLY:
                memories = self.memory.search(f"{message.sender} {message.subject} {message.body}")
                draft = self.response_agent.draft_reply(message, classification, memories)
                status = self.sender.send_email(message.sender, draft.subject, draft.body)
                self._log(message, action.value, status, draft.body[:500])
                summary.actions_taken += 1
            elif action == EmailAction.MARK_SPAM:
                if self.test_mode or self.settings.dry_run:
                    status = "dry_run"
                else:
                    self.reader.mark_spam(message.uid)
                    status = "ok"
                self._log(message, action.value, status, "Marked as spam or simulated.")
                summary.actions_taken += 1
            elif action == EmailAction.FORWARD:
                if not self.settings.forward_to_email:
                    self._log(message, action.value, "skipped", "FORWARD_TO_EMAIL is not configured.")
                    summary.skipped += 1
                    continue
                status = self.sender.forward_email(
                    self.settings.forward_to_email,
                    message,
                    note=f"Automated forward. Category={classification.category.value}, priority={classification.priority_score}.",
                )
                self._log(message, action.value, status, "Forwarded or simulated.")
                summary.actions_taken += 1
            elif action == EmailAction.NOTIFY:
                self.notifier.notify(
                    f"{classification.category.value.title()} email: {message.subject}",
                    message.preview,
                )
                self.voice.speak(f"Priority email from {message.sender}: {message.subject}")
                self._log(message, action.value, "ok", "Notification logged.")
                summary.actions_taken += 1
            elif action == EmailAction.SCHEDULE_MEETING:
                request = self.calendar.create_meeting_request(message)
                self._log(message, action.value, "pending_confirmation", str(request))
                summary.pending_confirmation += 1
            else:
                self._log(message, action.value, "noop", "No operation.")

    def _log(self, message: EmailMessage, action: str, status: str, details: str) -> None:
        logger.info("%s | %s | %s | %s", message.uid, action, status, details)
        self.db.log_action(ActionLog(email_uid=message.uid, action=action, status=status, details=details))
