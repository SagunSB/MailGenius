from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from agent import DecisionAgent, EmailAutomationAgent
from config import Settings
from email_classifier import LLMEmailClassifier
from models import EmailAction, EmailCategory
from sample_emails import load_sample_emails


def _output_dir() -> Path:
    path = Path("test_output") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_keyword_classifier_detects_spam() -> None:
    output = _output_dir()
    settings = Settings(spam_keywords=["crypto giveaway"], database_path=output / "db.sqlite")
    classifier = LLMEmailClassifier(settings)
    result = classifier.classify(load_sample_emails()[1])

    assert result.category == EmailCategory.SPAM
    assert not result.needs_reply


def test_decision_agent_never_replies_to_spam() -> None:
    output = _output_dir()
    settings = Settings(spam_keywords=["crypto giveaway"], database_path=output / "db.sqlite")
    classifier = LLMEmailClassifier(settings)
    classification = classifier.classify(load_sample_emails()[1])
    decision = DecisionAgent(settings).decide(classification)

    assert EmailAction.MARK_SPAM in decision.actions
    assert EmailAction.REPLY not in decision.actions


def test_agent_runs_one_cycle_in_test_mode() -> None:
    output = _output_dir()
    settings = Settings(
        max_emails_per_cycle=2,
        dry_run=True,
        require_confirmation=True,
        spam_keywords=["crypto giveaway"],
        database_path=output / "email_agent.db",
        memory_dir=output / "memory",
        attachment_dir=output / "attachments",
        log_file=output / "agent.log",
    )
    agent = EmailAutomationAgent(settings=settings, test_mode=True)

    summary = agent.run_once()

    assert summary.processed == 2
    assert summary.actions_taken >= 2
    assert not summary.errors
