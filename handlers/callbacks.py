"""Callback query handlers for the inline keyboards defined in
keyboards.py (account deletion confirmation, FSM cancellation)."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database import Database
from keyboards import build_confirm_delete_keyboard

logger = logging.getLogger(__name__)


def build_callbacks_router(database: Database, admin_ids: list[int]) -> Router:
    router = Router(name="callbacks")

    def is_admin(callback: CallbackQuery) -> bool:
        return callback.from_user is not None and callback.from_user.id in admin_ids

    @router.callback_query(lambda c: c.data == "fsm_cancel")
    async def cancel_fsm(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.answer("İptal edildi")
        if callback.message:
            await callback.message.edit_text("İşlem iptal edildi.")

    @router.callback_query(lambda c: c.data and c.data.startswith("account_delete:"))
    async def ask_delete_confirmation(callback: CallbackQuery) -> None:
        if not is_admin(callback):
            await callback.answer("Yetkiniz yok", show_alert=True)
            return
        username = callback.data.split(":", 1)[1]
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                f"@{username} takip listesinden silinsin mi?",
                reply_markup=build_confirm_delete_keyboard(username),
            )

    @router.callback_query(lambda c: c.data and c.data.startswith("account_delete_confirm:"))
    async def confirm_delete(callback: CallbackQuery) -> None:
        if not is_admin(callback):
            await callback.answer("Yetkiniz yok", show_alert=True)
            return
        username = callback.data.split(":", 1)[1]
        removed = await database.remove_account(username)
        await callback.answer()
        if callback.message:
            text = f"🗑 @{username} silindi." if removed else f"@{username} zaten listede değildi."
            await callback.message.edit_text(text)

    @router.callback_query(lambda c: c.data == "account_delete_cancel")
    async def cancel_delete(callback: CallbackQuery) -> None:
        await callback.answer("Vazgeçildi")
        if callback.message:
            await callback.message.edit_text("İşlem iptal edildi.")

    return router
