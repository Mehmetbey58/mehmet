"""Entry point. Wires configuration, the database, the Instagram client,
the Telegram bot and the scheduler together, then starts polling for
Telegram commands.

Instagram is never contacted from here directly - it is only ever
reached through ContentMonitor, which is itself only invoked by the
/anlik and /kontrol command handlers or by the one daily scheduled job.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_settings
from database import Database
from handlers.callbacks import build_callbacks_router
from handlers.commands import build_commands_router
from instagram import InstagramClient
from scheduler import ContentMonitor, SchedulerService
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_dir)

    database = Database(settings.database_path)
    await database.init()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    instagram_client = InstagramClient(settings)

    monitor = ContentMonitor(
        instagram=instagram_client,
        database=database,
        bot=bot,
        chat_ids=settings.admin_ids,
        post_fetch_limit=settings.post_fetch_limit,
    )

    scheduler_service = SchedulerService(
        monitor=monitor,
        check_time=settings.check_time,
        timezone=settings.timezone,
    )
    scheduler_service.start()

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(
        build_commands_router(
            monitor=monitor,
            database=database,
            instagram=instagram_client,
            admin_ids=settings.admin_ids,
        )
    )
    dispatcher.include_router(build_callbacks_router(database=database, admin_ids=settings.admin_ids))

    logger.info(
        "Bot başlatıldı. Telegram komutları dinleniyor; Instagram'a yalnızca "
        "/anlik, /kontrol ve günlük %s görevinde istek gönderilecek.",
        settings.check_time,
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler_service.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot durduruldu.")
