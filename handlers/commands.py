"""Telegram command handlers.

Only /anlik, /kontrol and the daily scheduled job (see scheduler.py)
ever cause a request to Instagram. Every other command here only reads
from or writes to the local SQLite database.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import Database
from instagram import InstagramClient
from keyboards import build_accounts_keyboard, build_cancel_keyboard
from scheduler import ContentMonitor
from states import AccountStates

logger = logging.getLogger(__name__)

_UNAUTHORIZED = "Bu botu kullanma yetkiniz yok."

_HELP_TEXT = (
    "<b>📷 Instagram Takip Botu</b>\n\n"
    "Belirlediğiniz Instagram hesaplarını takip eder; yeni gönderi, reel "
    "veya hikaye paylaşıldığında size Telegram üzerinden iletir.\n\n"
    "Instagram'a yalnızca şu durumlarda istek gönderilir:\n"
    "• <b>/anlik</b> çalıştırıldığında\n"
    "• <b>/kontrol kullaniciadi</b> çalıştırıldığında\n"
    "• Her gün ayarlanan saatte (varsayılan 09:00)\n\n"
    "<b>Komutlar</b>\n"
    "/ekle kullaniciadi - Takip listesine hesap ekler\n"
    "/sil kullaniciadi - Takip listesinden hesap kaldırır\n"
    "/liste - Takip edilen hesapları gösterir\n"
    "/anlik - Tüm hesapları şimdi kontrol eder\n"
    "/kontrol kullaniciadi - Sadece belirtilen hesabı kontrol eder\n"
    "/profil kullaniciadi - Hesap bilgilerini gösterir"
)


def build_commands_router(
    monitor: ContentMonitor,
    database: Database,
    instagram: InstagramClient,
    admin_ids: list[int],
) -> Router:
    router = Router(name="commands")

    def is_admin(message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in admin_ids

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        await message.answer(_HELP_TEXT)

    @router.message(Command("ekle"))
    async def cmd_add(message: Message, command: CommandObject, state: FSMContext) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        username = _clean_username(command.args)
        if not username:
            await state.set_state(AccountStates.waiting_for_add_username)
            await message.answer(
                "Eklemek istediğiniz Instagram kullanıcı adını gönderin:",
                reply_markup=build_cancel_keyboard(),
            )
            return
        await _do_add_account(message, database, username)

    @router.message(StateFilter(AccountStates.waiting_for_add_username))
    async def state_add_username(message: Message, state: FSMContext) -> None:
        username = _clean_username(message.text)
        await state.clear()
        if not username:
            await message.answer("Geçersiz kullanıcı adı.")
            return
        await _do_add_account(message, database, username)

    @router.message(Command("sil"))
    async def cmd_remove(message: Message, command: CommandObject, state: FSMContext) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        username = _clean_username(command.args)
        if not username:
            await state.set_state(AccountStates.waiting_for_remove_username)
            await message.answer(
                "Silmek istediğiniz Instagram kullanıcı adını gönderin:",
                reply_markup=build_cancel_keyboard(),
            )
            return
        await _do_remove_account(message, database, username)

    @router.message(StateFilter(AccountStates.waiting_for_remove_username))
    async def state_remove_username(message: Message, state: FSMContext) -> None:
        username = _clean_username(message.text)
        await state.clear()
        if not username:
            await message.answer("Geçersiz kullanıcı adı.")
            return
        await _do_remove_account(message, database, username)

    @router.message(Command("liste"))
    async def cmd_list(message: Message) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        accounts = await database.list_accounts()
        if not accounts:
            await message.answer("Takip edilen hesap yok.")
            return
        text = "Takip edilen hesaplar:\n" + "\n".join(f"• @{u}" for u in accounts)
        await message.answer(text, reply_markup=build_accounts_keyboard(accounts))

    @router.message(Command("anlik"))
    async def cmd_check_now(message: Message) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        await message.answer("🔎 Tüm hesaplar kontrol ediliyor...")
        result = await monitor.check_all_accounts()
        if result.sent_count == 0:
            await message.answer("Yeni içerik bulunamadı.")
        if result.failed_accounts:
            failed = ", ".join(f"@{u}" for u in result.failed_accounts)
            await message.answer(f"⚠️ Kontrol edilemeyen hesaplar: {failed}")

    @router.message(Command("kontrol"))
    async def cmd_check_one(message: Message, command: CommandObject) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        username = _clean_username(command.args)
        if not username:
            await message.answer("Kullanım: /kontrol kullaniciadi")
            return

        await message.answer(f"🔎 @{username} kontrol ediliyor...")
        try:
            sent = await monitor.check_account(username)
        except Exception:
            logger.exception("@%s kontrol edilirken hata oluştu", username)
            await message.answer(f"⚠️ @{username} kontrol edilirken bir hata oluştu.")
            return

        if sent == 0:
            await message.answer("Yeni içerik bulunamadı.")

    @router.message(Command("profil"))
    async def cmd_profile(message: Message, command: CommandObject, state: FSMContext) -> None:
        if not is_admin(message):
            await message.answer(_UNAUTHORIZED)
            return
        username = _clean_username(command.args)
        if not username:
            await state.set_state(AccountStates.waiting_for_profile_username)
            await message.answer(
                "Bilgilerini görmek istediğiniz Instagram kullanıcı adını gönderin:",
                reply_markup=build_cancel_keyboard(),
            )
            return
        await _do_show_profile(message, instagram, username)

    @router.message(StateFilter(AccountStates.waiting_for_profile_username))
    async def state_profile_username(message: Message, state: FSMContext) -> None:
        username = _clean_username(message.text)
        await state.clear()
        if not username:
            await message.answer("Geçersiz kullanıcı adı.")
            return
        await _do_show_profile(message, instagram, username)

    return router


async def _do_add_account(message: Message, database: Database, username: str) -> None:
    added = await database.add_account(username)
    await message.answer(f"✅ @{username} takip listesine eklendi." if added else f"@{username} zaten listede.")


async def _do_remove_account(message: Message, database: Database, username: str) -> None:
    removed = await database.remove_account(username)
    await message.answer(f"🗑 @{username} takip listesinden kaldırıldı." if removed else f"@{username} listede değil.")


async def _do_show_profile(message: Message, instagram: InstagramClient, username: str) -> None:
    try:
        profile = await instagram.fetch_profile_info(username)
    except Exception:
        logger.exception("@%s profili alınırken hata oluştu", username)
        await message.answer(f"⚠️ @{username} profili alınırken bir hata oluştu.")
        return

    if profile is None:
        await message.answer(f"@{username} bulunamadı.")
        return

    caption = (
        f"<b>{profile.full_name or profile.username}</b>\n"
        f"@{profile.username}\n\n"
        f"{profile.biography or ''}\n\n"
        f"👥 Takipçi: {profile.followers:,}\n"
        f"➡️ Takip edilen: {profile.followees:,}\n"
        f"🖼 Gönderi: {profile.media_count:,}"
    ).replace(",", ".")

    await message.answer_photo(photo=profile.profile_pic_url, caption=caption)


def _clean_username(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    return raw.strip().lstrip("@").split()[0]
