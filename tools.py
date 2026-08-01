from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import Settings
from models import EmailMessage


logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_actions_per_minute: int) -> None:
        self.max_actions = max_actions_per_minute
        self.timestamps: deque[float] = deque()

    def allow(self) -> bool:
        now = time.time()
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.max_actions:
            return False
        self.timestamps.append(now)
        return True


class NotificationTool:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def notify(self, title: str, message: str) -> str:
        logger.info("NOTIFICATION: %s | %s", title, message)
        return "logged"


class NotesTool:
    def __init__(self, base_dir: Path = Path("data/notes")) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_note(self, message: EmailMessage, content: str) -> Path:
        safe_uid = "".join(char for char in message.uid if char.isalnum() or char in {"-", "_"})
        path = self.base_dir / f"{safe_uid}.md"
        path.write_text(content, encoding="utf-8")
        return path


class CalendarTool:
    """A safe calendar stub that creates local calendar requests.

    Replace this class with Google Calendar or Microsoft Graph integration when
    OAuth credentials are available. The agent uses it through the same method.
    """

    def __init__(self, path: Path = Path("data/calendar_requests.jsonl")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_meeting_request(self, message: EmailMessage, title: str | None = None) -> dict:
        start = datetime.now(timezone.utc) + timedelta(days=1)
        request = {
            "source_email_uid": message.uid,
            "title": title or f"Follow-up: {message.subject}",
            "attendees": [message.sender],
            "suggested_start": start.isoformat(),
            "duration_minutes": 30,
            "status": "needs_confirmation",
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(request) + "\n")
        return request


class VoiceNotificationTool:
    def speak(self, message: str) -> str:
        logger.info("VOICE NOTIFICATION: %s", message)
        return "logged"
