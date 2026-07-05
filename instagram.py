"""Async facade over Instaloader - the only module in the codebase that
talks to Instagram.

Every public method here performs exactly one round of requests and
returns; nothing loops or polls on its own. Callers (the command
handlers and the daily scheduled job) decide *when* to call - this
module never decides that for itself. The login session is cached to
disk so the bot re-authenticates as rarely as possible.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from typing import Any

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    LoginRequiredException,
    ProfileNotExistsException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
)

from config import Settings
from models.instagram_models import ContentType, InstagramContent, MediaItem, MediaKind, ProfileInfo
from utils.retry import retry_async

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (ConnectionException, TooManyRequestsException)


class InstagramClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
        )
        self._login_lock = asyncio.Lock()
        self._logged_in = False

    async def _ensure_login(self) -> None:
        if self._logged_in:
            return
        async with self._login_lock:
            if self._logged_in:
                return
            await asyncio.to_thread(self._login_sync)
            self._logged_in = True

    def _login_sync(self) -> None:
        session_file = self._settings.ig_session_path
        username = self._settings.ig_username

        if session_file.exists():
            try:
                logger.info("Kayıtlı Instagram oturumu yükleniyor: %s", session_file)
                self._loader.load_session_from_file(username, str(session_file))
                return
            except (FileNotFoundError, LoginRequiredException):
                logger.warning("Kayıtlı oturum geçersiz, yeniden giriş yapılacak")

        session_file.parent.mkdir(parents=True, exist_ok=True)
        self._loader.login(username, self._settings.ig_password)
        self._loader.save_session_to_file(str(session_file))
        logger.info("Instagram girişi başarılı, oturum diske kaydedildi")

    # -- posts / reels ------------------------------------------------
    @retry_async(exceptions=_RETRYABLE_EXCEPTIONS, attempts=3, base_delay=5.0)
    async def fetch_recent_posts(self, username: str, limit: int) -> list[InstagramContent]:
        await self._ensure_login()
        return await asyncio.to_thread(self._fetch_recent_posts_sync, username, limit)

    def _fetch_recent_posts_sync(self, username: str, limit: int) -> list[InstagramContent]:
        try:
            profile = instaloader.Profile.from_username(self._loader.context, username)
        except (ProfileNotExistsException, QueryReturnedNotFoundException):
            logger.error("Hesap bulunamadı: @%s", username)
            return []

        posts = itertools.islice(profile.get_posts(), limit)
        return [self._post_to_content(post, username) for post in posts]

    def _post_to_content(self, post: Any, username: str) -> InstagramContent:
        if post.typename == "GraphSidecar":
            items = [self._sidecar_node_to_media_item(node) for node in post.get_sidecar_nodes()]
            content_type = ContentType.CAROUSEL
        elif post.is_video:
            # Instagram's feed videos are, today, effectively Reels.
            items = [MediaItem(url=post.video_url, kind=MediaKind.VIDEO)]
            content_type = ContentType.REEL
        else:
            items = [MediaItem(url=post.url, kind=MediaKind.PHOTO)]
            content_type = ContentType.POST

        return InstagramContent(
            media_id=str(post.mediaid),
            username=username,
            content_type=content_type,
            taken_at=post.date_utc,
            media_items=items,
            caption=(post.caption or None),
        )

    @staticmethod
    def _sidecar_node_to_media_item(node: Any) -> MediaItem:
        if node.is_video:
            return MediaItem(url=node.video_url, kind=MediaKind.VIDEO)
        return MediaItem(url=node.display_url, kind=MediaKind.PHOTO)

    # -- stories -------------------------------------------------------
    @retry_async(exceptions=_RETRYABLE_EXCEPTIONS, attempts=3, base_delay=5.0)
    async def fetch_active_stories(self, username: str) -> list[InstagramContent]:
        await self._ensure_login()
        return await asyncio.to_thread(self._fetch_active_stories_sync, username)

    def _fetch_active_stories_sync(self, username: str) -> list[InstagramContent]:
        try:
            profile = instaloader.Profile.from_username(self._loader.context, username)
        except (ProfileNotExistsException, QueryReturnedNotFoundException):
            logger.error("Hesap bulunamadı: @%s", username)
            return []

        contents: list[InstagramContent] = []
        for story in self._loader.get_stories(userids=[profile.userid]):
            for item in story.get_items():
                contents.append(self._story_item_to_content(item, username))
        return contents

    def _story_item_to_content(self, item: Any, username: str) -> InstagramContent:
        if item.is_video:
            media_item = MediaItem(url=item.video_url, kind=MediaKind.VIDEO)
        else:
            media_item = MediaItem(url=item.url, kind=MediaKind.PHOTO)

        # Instagram does not expose story text-overlay content through a
        # stable public field; this is a best-effort approximation and
        # will often be empty.
        caption = getattr(item, "caption", None) or None

        return InstagramContent(
            media_id=str(item.mediaid),
            username=username,
            content_type=ContentType.STORY,
            taken_at=item.date_utc,
            media_items=[media_item],
            caption=caption,
        )

    # -- profile info ---------------------------------------------------
    @retry_async(exceptions=_RETRYABLE_EXCEPTIONS, attempts=3, base_delay=5.0)
    async def fetch_profile_info(self, username: str) -> ProfileInfo | None:
        await self._ensure_login()
        return await asyncio.to_thread(self._fetch_profile_info_sync, username)

    def _fetch_profile_info_sync(self, username: str) -> ProfileInfo | None:
        try:
            profile = instaloader.Profile.from_username(self._loader.context, username)
        except (ProfileNotExistsException, QueryReturnedNotFoundException):
            logger.error("Hesap bulunamadı: @%s", username)
            return None

        return ProfileInfo(
            username=profile.username,
            full_name=profile.full_name,
            biography=profile.biography,
            followers=profile.followers,
            followees=profile.followees,
            media_count=profile.mediacount,
            profile_pic_url=profile.profile_pic_url,
        )
