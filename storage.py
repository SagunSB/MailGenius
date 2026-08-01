from __future__ import annotations

import sqlite3
from pathlib import Path

from models import ActionLog, ClassificationResult, EmailMessage


class EmailDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emails (
                    uid TEXT PRIMARY KEY,
                    sender TEXT,
                    recipients TEXT,
                    subject TEXT,
                    body TEXT,
                    received_at TEXT,
                    category TEXT,
                    priority_score INTEGER,
                    intent TEXT,
                    risk_level TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_uid TEXT,
                    action TEXT,
                    status TEXT,
                    details TEXT,
                    created_at TEXT
                )
                """
            )

    def save_email(self, message: EmailMessage, classification: ClassificationResult) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO emails
                (uid, sender, recipients, subject, body, received_at, category, priority_score, intent, risk_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.uid,
                    message.sender,
                    ",".join(message.recipients),
                    message.subject,
                    message.body,
                    message.received_at.isoformat(),
                    classification.category.value,
                    classification.priority_score,
                    classification.intent,
                    classification.risk_level,
                ),
            )

    def log_action(self, log: ActionLog) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO actions (email_uid, action, status, details, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (log.email_uid, log.action, log.status, log.details, log.created_at.isoformat()),
            )

    def recent_actions(self, limit: int = 25) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM actions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_emails(self, limit: int = 25) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    e.*,
                    COUNT(a.id) AS action_count,
                    MAX(a.created_at) AS last_action_at
                FROM emails e
                LEFT JOIN actions a ON a.email_uid = e.uid
                GROUP BY e.uid
                ORDER BY COALESCE(MAX(a.created_at), e.received_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def email_detail(self, uid: str) -> dict | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            email_row = conn.execute("SELECT * FROM emails WHERE uid = ?", (uid,)).fetchone()
            if email_row is None:
                return None
            actions = conn.execute(
                "SELECT * FROM actions WHERE email_uid = ? ORDER BY created_at DESC",
                (uid,),
            ).fetchall()
        detail = dict(email_row)
        detail["actions"] = [dict(row) for row in actions]
        return detail

    def summary(self) -> dict:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            email_count = conn.execute("SELECT COUNT(*) AS count FROM emails").fetchone()["count"]
            action_count = conn.execute("SELECT COUNT(*) AS count FROM actions").fetchone()["count"]
            pending_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM actions
                WHERE status LIKE '%pending%' OR action = 'confirmation_required'
                """
            ).fetchone()["count"]
            spam_count = conn.execute(
                "SELECT COUNT(*) AS count FROM emails WHERE category = 'spam'"
            ).fetchone()["count"]
            urgent_count = conn.execute(
                "SELECT COUNT(*) AS count FROM emails WHERE category = 'urgent'"
            ).fetchone()["count"]
            last_action = conn.execute(
                "SELECT created_at FROM actions ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            category_rows = conn.execute(
                "SELECT category, COUNT(*) AS count FROM emails GROUP BY category ORDER BY count DESC"
            ).fetchall()
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM actions GROUP BY status ORDER BY count DESC"
            ).fetchall()
        return {
            "emails": email_count,
            "actions": action_count,
            "pending": pending_count,
            "spam": spam_count,
            "urgent": urgent_count,
            "last_action_at": last_action["created_at"] if last_action else None,
            "categories": [dict(row) for row in category_rows],
            "statuses": [dict(row) for row in status_rows],
        }
