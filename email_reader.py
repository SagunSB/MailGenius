from __future__ import annotations

import email
import imaplib
import logging
import smtplib
from datetime import datetime, timezone
from email.header import decode_header
from email.message import EmailMessage as StdEmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from models import EmailMessage


logger = logging.getLogger(__name__)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded: list[str] = []
    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


class EmailReader:
    def __init__(
        self,
        email_address: str,
        password: str,
        imap_host: str,
        imap_port: int,
        attachment_dir: Path,
    ) -> None:
        self.email_address = email_address
        self.password = password
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.attachment_dir = attachment_dir

    def fetch_unread(self, limit: int = 5) -> list[EmailMessage]:
        if not self.email_address or not self.password:
            raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD are required for live IMAP fetching.")

        messages: list[EmailMessage] = []
        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as mail:
            mail.login(self.email_address, self.password)
            mail.select("INBOX")
            status, data = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("IMAP search failed: %s", status)
                return messages

            uids = data[0].split()[:limit]
            for uid_bytes in uids:
                uid = uid_bytes.decode()
                status, msg_data = mail.fetch(uid_bytes, "(RFC822)")
                if status != "OK":
                    logger.warning("Failed to fetch email UID %s", uid)
                    continue
                raw_email = msg_data[0][1]
                parsed = email.message_from_bytes(raw_email)
                messages.append(self._parse_message(uid, parsed))
        return messages

    def mark_seen(self, uid: str) -> None:
        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as mail:
            mail.login(self.email_address, self.password)
            mail.select("INBOX")
            mail.store(uid, "+FLAGS", "\\Seen")

    def mark_spam(self, uid: str) -> None:
        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as mail:
            mail.login(self.email_address, self.password)
            mail.select("INBOX")
            mail.store(uid, "+X-GM-LABELS", "\\Spam")

    def _parse_message(self, uid: str, msg: StdEmailMessage) -> EmailMessage:
        body = ""
        attachments: list[dict[str, str]] = []
        self.attachment_dir.mkdir(parents=True, exist_ok=True)

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                content_type = part.get_content_type()
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                elif "attachment" in content_disposition:
                    filename = _decode(part.get_filename())
                    if filename:
                        safe_name = f"{uid}_{Path(filename).name}"
                        path = self.attachment_dir / safe_name
                        payload = part.get_payload(decode=True)
                        if payload:
                            path.write_bytes(payload)
                            attachments.append({"filename": filename, "path": str(path)})
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

        received_at = datetime.now(timezone.utc)
        if msg.get("Date"):
            try:
                received_at = email.utils.parsedate_to_datetime(msg["Date"])
            except (TypeError, ValueError):
                pass

        return EmailMessage(
            uid=uid,
            sender=_decode(msg.get("From")),
            recipients=[_decode(msg.get("To"))],
            subject=_decode(msg.get("Subject")),
            body=body.strip(),
            received_at=received_at,
            message_id=msg.get("Message-ID"),
            attachments=attachments,
        )


class EmailSender:
    def __init__(
        self,
        email_address: str,
        password: str,
        smtp_host: str,
        smtp_port: int,
        dry_run: bool = True,
    ) -> None:
        self.email_address = email_address
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.dry_run = dry_run

    def send_email(self, to_email: str, subject: str, body: str) -> str:
        if self.dry_run:
            logger.info("DRY RUN: would send email to=%s subject=%s", to_email, subject)
            return "dry_run"
        if not self.email_address or not self.password:
            raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD are required for SMTP sending.")

        msg = MIMEMultipart()
        msg["From"] = self.email_address
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.email_address, self.password)
            server.send_message(msg)
        return "sent"

    def forward_email(self, to_email: str, original: EmailMessage, note: str = "") -> str:
        subject = f"Fwd: {original.subject}"
        body = (
            f"{note}\n\n"
            f"From: {original.sender}\n"
            f"Received: {original.received_at.isoformat()}\n"
            f"Subject: {original.subject}\n\n"
            f"{original.body}"
        ).strip()
        return self.send_email(to_email, subject, body)
