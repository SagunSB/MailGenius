from __future__ import annotations

from datetime import datetime, timezone

from models import EmailMessage


def load_sample_emails() -> list[EmailMessage]:
    return [
        EmailMessage(
            uid="sample-001",
            sender="client@example.com",
            recipients=["you@example.com"],
            subject="Urgent: proposal deadline moved to today",
            body=(
                "Hi, the client review deadline moved up. Can you send the updated proposal "
                "and join a quick call this afternoon?"
            ),
            received_at=datetime.now(timezone.utc),
        ),
        EmailMessage(
            uid="sample-002",
            sender="newsletter@random-crypto.example",
            recipients=["you@example.com"],
            subject="Crypto giveaway winner",
            body="Congratulations, you won a crypto giveaway. Send wallet details immediately.",
            received_at=datetime.now(timezone.utc),
        ),
        EmailMessage(
            uid="sample-003",
            sender="sibling@example.com",
            recipients=["you@example.com"],
            subject="Birthday dinner plans",
            body="Are you free for family birthday dinner on Saturday?",
            received_at=datetime.now(timezone.utc),
        ),
        EmailMessage(
            uid="sample-004",
            sender="manager@example.com",
            recipients=["you@example.com"],
            subject="Weekly report",
            body="Please save the project status report notes and send a short acknowledgement.",
            received_at=datetime.now(timezone.utc),
        ),
    ]
