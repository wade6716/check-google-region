"""Configuration management for check-google-region.

Zero-dependency configuration reader that supports:
- System environment variables
- Optional local .env file
- Platform-aware defaults
"""

import os
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Lightweight .env parser without external dependencies.
    Does not overwrite existing environment variables.
    """
    if not os.path.isfile(dotenv_path):
        return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# Automatically load .env if present
load_dotenv()


def get_default_state_file() -> str:
    """Return platform-default state cache file path."""
    if os.name == "nt":
        return os.path.join(tempfile.gettempdir(), "last_google_country.json")
    return "/var/tmp/last_google_country.json"


@dataclass
class Config:
    state_file: str
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    receiver_email: str
    insecure_ssl: bool
    proxy: Optional[str]
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    webhook_url: Optional[str]

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            state_file=os.getenv("STATE_FILE", get_default_state_file()),
            smtp_server=os.getenv("SMTP_SERVER", "smtp.qq.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "465")),
            smtp_user=os.getenv("SMTP_USER", "your_email@qq.com"),
            smtp_pass=os.getenv("SMTP_PASS", "your_smtp_auth_token"),
            receiver_email=os.getenv("RECEIVER_EMAIL", "target@example.com"),
            insecure_ssl=os.getenv("INSECURE_SSL", "false").lower() in ("true", "1", "yes"),
            proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("ALL_PROXY"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            webhook_url=os.getenv("WEBHOOK_URL"),
        )
