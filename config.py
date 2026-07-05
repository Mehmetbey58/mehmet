"""Application configuration.

All runtime configuration is loaded from environment variables (via a
.env file in development). Nothing else in the codebase reads
`os.environ` directly - every other module receives a `Settings`
instance through dependency injection.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_CHECK_TIME = "09:00"
_DEFAULT_DATABASE_PATH = "data/bot.db"
_DEFAULT_SESSION_PATH = "data/ig_session"
_DEFAULT_LOG_DIR = "logs"
_DEFAULT_POST_FETCH_LIMIT = 5
_DEFAULT_TIMEZONE = "Europe/Istanbul"


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_ids: list[int]
    ig_username: str
    ig_password: str
    database_path: Path
    ig_session_path: Path
    check_time: str
    post_fetch_limit: int
    log_dir: Path
    timezone: str


def load_settings() -> Settings:
    """Load and validate configuration. Fails fast at startup with a
    clear error if anything required is missing, instead of surfacing a
    confusing error later at runtime."""
    return Settings(
        bot_token=_require("BOT_TOKEN"),
        admin_ids=_parse_admin_ids(_require("ADMIN_IDS")),
        ig_username=_require("IG_USERNAME"),
        ig_password=_require("IG_PASSWORD"),
        database_path=Path(os.getenv("DATABASE_PATH", _DEFAULT_DATABASE_PATH)),
        ig_session_path=Path(os.getenv("IG_SESSION_PATH", _DEFAULT_SESSION_PATH)),
        check_time=_validate_time(os.getenv("CHECK_TIME", _DEFAULT_CHECK_TIME)),
        post_fetch_limit=int(os.getenv("POST_FETCH_LIMIT", str(_DEFAULT_POST_FETCH_LIMIT))),
        log_dir=Path(os.getenv("LOG_DIR", _DEFAULT_LOG_DIR)),
        timezone=os.getenv("TIMEZONE", _DEFAULT_TIMEZONE),
    )


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Ortam değişkeni eksik veya boş: {name}")
    return value


def _parse_admin_ids(raw: str) -> list[int]:
    try:
        return [int(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise RuntimeError("ADMIN_IDS sadece virgülle ayrılmış sayılardan oluşmalı") from exc


def _validate_time(value: str) -> str:
    try:
        hour_str, minute_str = value.split(":")
        hour, minute = int(hour_str), int(minute_str)
    except ValueError as exc:
        raise RuntimeError("CHECK_TIME formatı SS:DD olmalı, örn. 09:00") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RuntimeError("CHECK_TIME geçerli bir saat olmalı (00:00 - 23:59)")
    return value
