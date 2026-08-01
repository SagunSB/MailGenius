from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'python-dotenv'. Install project dependencies with: "
        "python -m pip install -r requirements.txt"
    ) from exc


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_list(value: str | None, default: list[str] | None = None) -> list[str]:
    if not value:
        return default or []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    dry_run: bool = True
    require_confirmation: bool = True
    max_emails_per_cycle: int = 5
    loop_interval_seconds: int = 300
    rate_limit_actions_per_minute: int = 10

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    email_provider: str = "gmail"
    email_address: str = ""
    email_password: str = ""
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    forward_to_email: str = ""
    notify_email: str = ""
    auto_reply_categories: list[str] = field(default_factory=lambda: ["work", "personal"])
    forward_categories: list[str] = field(default_factory=lambda: ["urgent"])
    spam_keywords: list[str] = field(default_factory=list)

    memory_backend: str = "local"
    memory_dir: Path = Path("data/memory")
    database_path: Path = Path("data/email_agent.db")
    attachment_dir: Path = Path("data/attachments")
    log_file: Path = Path("logs/email_agent.log")

    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000

    @classmethod
    def load(cls) -> "Settings":
        for env_file in (".env", "config.env"):
            if Path(env_file).exists():
                load_dotenv(env_file)
                break

        return cls(
            dry_run=_as_bool(os.getenv("DRY_RUN"), True),
            require_confirmation=_as_bool(os.getenv("REQUIRE_CONFIRMATION"), True),
            max_emails_per_cycle=int(os.getenv("MAX_EMAILS_PER_CYCLE", "5")),
            loop_interval_seconds=int(os.getenv("LOOP_INTERVAL_SECONDS", "300")),
            rate_limit_actions_per_minute=int(os.getenv("RATE_LIMIT_ACTIONS_PER_MINUTE", "10")),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            email_provider=os.getenv("EMAIL_PROVIDER", "gmail"),
            email_address=os.getenv("EMAIL_ADDRESS", ""),
            email_password=os.getenv("EMAIL_PASSWORD", ""),
            imap_host=os.getenv("IMAP_HOST", "imap.gmail.com"),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            forward_to_email=os.getenv("FORWARD_TO_EMAIL", ""),
            notify_email=os.getenv("NOTIFY_EMAIL", ""),
            auto_reply_categories=_as_list(os.getenv("AUTO_REPLY_CATEGORIES"), ["work", "personal"]),
            forward_categories=_as_list(os.getenv("FORWARD_CATEGORIES"), ["urgent"]),
            spam_keywords=_as_list(os.getenv("SPAM_KEYWORDS")),
            memory_backend=os.getenv("MEMORY_BACKEND", "local").lower(),
            memory_dir=Path(os.getenv("MEMORY_DIR", "data/memory")),
            database_path=Path(os.getenv("DATABASE_PATH", "data/email_agent.db")),
            attachment_dir=Path(os.getenv("ATTACHMENT_DIR", "data/attachments")),
            log_file=Path(os.getenv("LOG_FILE", "logs/email_agent.log")),
            dashboard_host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
            dashboard_port=int(os.getenv("DASHBOARD_PORT", "8000")),
        )
