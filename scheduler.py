"""Orchestrates Instagram checks and the single daily scheduled job.

`ContentMonitor` is the one choke point every Instagram request flows
through: it fetches, deduplicates against the database, delivers to
Telegram, and persists. It is only ever invoked by command handlers
(/anlik, /kontrol) or by `SchedulerService`'s one daily cron job - never
by a timer/poll loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Database
from instagram import InstagramClient
from models.instagram_models import InstagramContent
from utils.senders import send_content

logger = logging.getLogger(__name__)

_DAILY_JOB_ID = "daily_instagram_check"


@dataclass(slots=True)
class CheckResult:
    sent_count: int = 0
    checked_accounts: int = 0
    failed_accounts: list[str] = field(default_factory=list)


class ContentMonitor:
    def __init__(
        self,
        instagram: InstagramClient,
        database: Database,
        bot: Bot,
        chat_ids: list[int],
        post_fetch_limit: int,
    ) -> None:
        self._instagram = instagram
        self._database = database
        self._bot = bot
        self._chat_ids = chat_ids
        self._post_fetch_limit = post_fetch_limit

    async def check_all_accounts(self) -> CheckResult:
        result = CheckResult()
        accounts = await self._database.list_accounts()
        for username in accounts:
            result.checked_accounts += 1
            try:
                result.sent_count += await self.check_account(username)
            except Exception:
                logger.exception("@%s kontrol edilirken hata oluştu", username)
                result.failed_accounts.append(username)

        await self._database.set_setting("last_check_at", _utc_now_iso())
        return result

    async def check_account(self, username: str) -> int:
        """Check a single account and deliver any new content. Never
        raises for expected failure modes (network errors, unknown
        account) - those are logged and result in zero new items so a
        single bad account never brings the bot down."""
        posts = await self._instagram.fetch_recent_posts(username, self._post_fetch_limit)
        stories = await self._instagram.fetch_active_stories(username)

        new_items: list[InstagramContent] = []
        for content in posts + stories:
            already_sent = await self._database.is_sent(
                content.content_type.value, content.username, content.media_id
            )
            if not already_sent:
                new_items.append(content)

        new_items.sort(key=lambda c: c.taken_at)

        for content in new_items:
            await self._database.cache_content(content)
            await self._deliver(content)

        return len(new_items)

    async def _deliver(self, content: InstagramContent) -> None:
        for chat_id in self._chat_ids:
            await send_content(self._bot, chat_id, content)
            await self._database.mark_sent(
                content.content_type.value, content.username, content.media_id, chat_id
            )


class SchedulerService:
    """Thin APScheduler wrapper. Registers exactly one cron job that
    fires once a day - no interval/polling jobs are ever added."""

    def __init__(self, monitor: ContentMonitor, check_time: str, timezone: str) -> None:
        self._monitor = monitor
        self._check_time = check_time
        self._timezone = timezone
        self._scheduler = AsyncIOScheduler(timezone=timezone)

    def start(self) -> None:
        hour, minute = _parse_time(self._check_time)
        self._scheduler.add_job(
            self._run_daily_check,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=self._timezone),
            id=_DAILY_JOB_ID,
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Günlük Instagram kontrolü %02d:%02d (%s) saatine planlandı", hour, minute, self._timezone)

    async def _run_daily_check(self) -> None:
        logger.info("Günlük otomatik kontrol başlıyor")
        result = await self._monitor.check_all_accounts()
        logger.info(
            "Günlük kontrol tamamlandı: %s hesap kontrol edildi, %s yeni içerik gönderildi, %s hata",
            result.checked_accounts,
            result.sent_count,
            len(result.failed_accounts),
        )

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)


def _parse_time(value: str) -> tuple[int, int]:
    hour_str, minute_str = value.split(":")
    return int(hour_str), int(minute_str)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
