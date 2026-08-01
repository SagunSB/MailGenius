from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from rich.panel import Panel
from rich.table import Table


class EmailCategory(str, Enum):
    IMPORTANT = "important"
    SPAM = "spam"
    WORK = "work"
    PERSONAL = "personal"
    URGENT = "urgent"


class EmailAction(str, Enum):
    REPLY = "reply"
    MARK_SPAM = "mark_spam"
    FORWARD = "forward"
    SAVE = "save"
    NOTIFY = "notify"
    SCHEDULE_MEETING = "schedule_meeting"
    NOOP = "noop"


@dataclass
class EmailMessage:
    uid: str
    sender: str
    recipients: list[str]
    subject: str
    body: str
    received_at: datetime
    message_id: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)

    @property
    def preview(self) -> str:
        text = " ".join(self.body.split())
        return text[:220] + ("..." if len(text) > 220 else "")


class ClassificationResult(BaseModel):
    category: EmailCategory
    priority_score: int = Field(ge=1, le=10)
    intent: str
    sentiment: str = "neutral"
    risk_level: str = Field(pattern="^(low|medium|high)$")
    needs_reply: bool
    needs_scheduling: bool = False
    reasoning: str


class AgentDecision(BaseModel):
    actions: list[EmailAction]
    requires_confirmation: bool
    reason: str


class ReplyDraft(BaseModel):
    subject: str
    body: str
    tone: str


@dataclass
class ActionLog:
    email_uid: str
    action: str
    status: str
    details: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CycleSummary:
    processed: int = 0
    actions_taken: int = 0
    pending_confirmation: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_panel(self) -> Panel:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column()
        table.add_row("Processed", str(self.processed))
        table.add_row("Actions", str(self.actions_taken))
        table.add_row("Pending confirmation", str(self.pending_confirmation))
        table.add_row("Skipped", str(self.skipped))
        if self.errors:
            table.add_row("Errors", "\n".join(self.errors[:5]))
        return Panel(table, title="Email Agent Cycle", border_style="green")
