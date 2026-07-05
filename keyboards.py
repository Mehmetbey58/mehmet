"""Inline keyboards used across the bot's handlers."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_accounts_keyboard(usernames: list[str]) -> InlineKeyboardMarkup:
    """One delete button per tracked account, shown under /liste output."""
    buttons = [
        [InlineKeyboardButton(text=f"🗑 @{username}", callback_data=f"account_delete:{username}")]
        for username in usernames
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_confirm_delete_keyboard(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Evet, sil", callback_data=f"account_delete_confirm:{username}"),
                InlineKeyboardButton(text="❌ Vazgeç", callback_data="account_delete_cancel"),
            ]
        ]
    )


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ İptal", callback_data="fsm_cancel")]]
    )
