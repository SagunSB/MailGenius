from __future__ import annotations

import json
import logging

from openai import OpenAI
from pydantic import ValidationError

from config import Settings
from models import ClassificationResult, EmailCategory, ReplyDraft, EmailMessage


logger = logging.getLogger(__name__)


class LLMEmailClassifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def classify(self, message: EmailMessage) -> ClassificationResult:
        keyword_result = self._keyword_classify(message)
        if not self.client:
            return keyword_result

        prompt = {
            "sender": message.sender,
            "subject": message.subject,
            "body_preview": message.preview,
            "allowed_categories": [category.value for category in EmailCategory],
        }
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You classify emails for an automation agent. "
                            "Return only JSON with keys: category, priority_score, intent, "
                            "sentiment, risk_level, needs_reply, needs_scheduling, reasoning."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return ClassificationResult.model_validate_json(content)
        except (ValidationError, Exception) as exc:
            logger.warning("LLM classification failed, using fallback: %s", exc)
            return keyword_result

    def _keyword_classify(self, message: EmailMessage) -> ClassificationResult:
        text = f"{message.sender} {message.subject} {message.body}".lower()
        spam_hit = any(keyword in text for keyword in self.settings.spam_keywords)
        urgent_hit = any(word in text for word in ["urgent", "asap", "immediately", "deadline", "critical"])
        meeting_hit = any(word in text for word in ["meeting", "calendar", "schedule", "call", "zoom"])
        work_hit = any(word in text for word in ["project", "client", "invoice", "deadline", "report", "proposal"])

        if spam_hit:
            category = EmailCategory.SPAM
            score = 1
            risk = "high"
            needs_reply = False
        elif urgent_hit:
            category = EmailCategory.URGENT
            score = 9
            risk = "medium"
            needs_reply = True
        elif work_hit:
            category = EmailCategory.WORK
            score = 7
            risk = "low"
            needs_reply = True
        elif "family" in text or "dinner" in text or "birthday" in text:
            category = EmailCategory.PERSONAL
            score = 5
            risk = "low"
            needs_reply = True
        else:
            category = EmailCategory.IMPORTANT
            score = 6
            risk = "medium"
            needs_reply = False

        return ClassificationResult(
            category=category,
            priority_score=score,
            intent="Heuristic classification based on sender, subject, and body keywords.",
            sentiment="neutral",
            risk_level=risk,
            needs_reply=needs_reply,
            needs_scheduling=meeting_hit,
            reasoning="OpenAI API unavailable or fallback selected; used local keyword policy.",
        )


class ResponseAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def draft_reply(self, message: EmailMessage, classification: ClassificationResult, memories: list[str]) -> ReplyDraft:
        if not self.client:
            return ReplyDraft(
                subject=f"Re: {message.subject}",
                body=(
                    f"Hi,\n\nThanks for your email about {classification.intent.lower()} "
                    "I have received it and will follow up shortly.\n\nBest regards"
                ),
                tone="professional",
            )

        memory_text = "\n".join(f"- {memory}" for memory in memories[:5]) or "No relevant prior memory."
        prompt = (
            f"Email from: {message.sender}\n"
            f"Subject: {message.subject}\n"
            f"Body:\n{message.body[:4000]}\n\n"
            f"Classification: {classification.model_dump_json()}\n"
            f"Relevant prior interactions:\n{memory_text}\n\n"
            "Draft a concise, context-aware professional reply. "
            "Return JSON with keys subject, body, tone."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.4,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write safe email reply drafts. Never promise unavailable facts, "
                            "financial commitments, legal advice, or confidential data."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            return ReplyDraft.model_validate_json(response.choices[0].message.content or "{}")
        except Exception as exc:
            logger.warning("Reply draft failed, using fallback: %s", exc)
            return ReplyDraft(
                subject=f"Re: {message.subject}",
                body="Hi,\n\nThanks for reaching out. I received your message and will review it shortly.\n\nBest regards",
                tone="professional",
            )
