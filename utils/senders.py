"""Delivers Instagram content to Telegram following the bot's fixed
message layout rules (media first, caption as a separate message for
posts/reels/carousels; media with an inline caption for stories)."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import InputMediaPhoto, InputMediaVideo

from models.instagram_models import ContentType, InstagramContent, MediaKind

_CAPTION_PREFIX = "📝 "


async def send_content(bot: Bot, chat_id: int, content: InstagramContent) -> None:
    if content.content_type == ContentType.STORY:
        await _send_story(bot, chat_id, content)
    else:
        await _send_post(bot, chat_id, content)


async def _send_post(bot: Bot, chat_id: int, content: InstagramContent) -> None:
    if content.content_type == ContentType.CAROUSEL:
        media_group = [
            InputMediaPhoto(media=item.url) if item.kind == MediaKind.PHOTO else InputMediaVideo(media=item.url)
            for item in content.media_items
        ]
        await bot.send_media_group(chat_id, media=media_group)
    else:
        item = content.media_items[0]
        if item.kind == MediaKind.VIDEO:
            await bot.send_video(chat_id, video=item.url)
        else:
            await bot.send_photo(chat_id, photo=item.url)

    # Caption is always a separate message for posts/reels/carousels -
    # and is skipped entirely when there is no caption.
    if content.caption:
        await bot.send_message(chat_id, f"{_CAPTION_PREFIX}{content.caption}")


async def _send_story(bot: Bot, chat_id: int, content: InstagramContent) -> None:
    item = content.media_items[0]
    caption = content.caption or None
    if item.kind == MediaKind.VIDEO:
        await bot.send_video(chat_id, video=item.url, caption=caption)
    else:
        await bot.send_photo(chat_id, photo=item.url, caption=caption)
