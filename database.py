"""Async SQLite persistence layer.

Tables:
    accounts      - Instagram usernames the bot is tracking.
    posts         - discovered feed posts (photo/carousel) per account.
    reels         - discovered reels per account.
    stories       - discovered stories per account.
    sent_messages - authoritative record of what has actually been sent
                    to Telegram, keyed by Instagram Media ID. This is
                    what prevents duplicate sends.
    settings      - small key/value store for runtime state.

Every method opens and closes its own connection. For a low-traffic,
single-process bot this is simpler and safer than sharing one
long-lived connection across concurrent asyncio tasks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from models.instagram_models import ContentType, InstagramContent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    media_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    caption TEXT,
    taken_at TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    UNIQUE(username, media_id)
);

CREATE TABLE IF NOT EXISTS reels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    media_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    caption TEXT,
    taken_at TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    UNIQUE(username, media_id)
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    media_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    caption TEXT,
    taken_at TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    UNIQUE(username, media_id)
);

CREATE TABLE IF NOT EXISTS sent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL,
    username TEXT NOT NULL,
    media_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    UNIQUE(content_type, username, media_id, chat_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_CONTENT_TABLES: dict[ContentType, str] = {
    ContentType.POST: "posts",
    ContentType.CAROUSEL: "posts",
    ContentType.REEL: "reels",
    ContentType.STORY: "stories",
}


class Database:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.executescript(_SCHEMA)
            await conn.commit()

    # -- accounts ---------------------------------------------------
    async def add_account(self, username: str) -> bool:
        async with aiosqlite.connect(self._db_path) as conn:
            try:
                await conn.execute(
                    "INSERT INTO accounts (username, added_at) VALUES (?, ?)",
                    (username, _now_iso()),
                )
                await conn.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_account(self, username: str) -> bool:
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute("DELETE FROM accounts WHERE username = ?", (username,))
            await conn.commit()
            return cursor.rowcount > 0

    async def list_accounts(self) -> list[str]:
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute("SELECT username FROM accounts ORDER BY username")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # -- content cache + dedup ---------------------------------------
    async def cache_content(self, content: InstagramContent) -> None:
        table = _CONTENT_TABLES[content.content_type]
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                f"INSERT OR IGNORE INTO {table} "
                "(username, media_id, media_type, caption, taken_at, discovered_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    content.username,
                    content.media_id,
                    content.content_type.value,
                    content.caption,
                    content.taken_at.isoformat(),
                    _now_iso(),
                ),
            )
            await conn.commit()

    async def is_sent(self, content_type: str, username: str, media_id: str) -> bool:
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM sent_messages WHERE content_type = ? AND username = ? AND media_id = ?",
                (content_type, username, media_id),
            )
            return await cursor.fetchone() is not None

    async def mark_sent(self, content_type: str, username: str, media_id: str, chat_id: int) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO sent_messages "
                "(content_type, username, media_id, chat_id, sent_at) VALUES (?, ?, ?, ?, ?)",
                (content_type, username, media_id, chat_id, _now_iso()),
            )
            await conn.commit()

    # -- settings ------------------------------------------------------
    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
