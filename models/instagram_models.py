"""Data models shared between the Instagram client and the rest of the
bot. Kept as plain, immutable dataclasses - no ORM, no framework
coupling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ContentType(str, Enum):
    POST = "post"
    REEL = "reel"
    CAROUSEL = "carousel"
    STORY = "story"


class MediaKind(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class MediaItem:
    url: str
    kind: MediaKind


@dataclass(frozen=True, slots=True)
class InstagramContent:
    media_id: str
    username: str
    content_type: ContentType
    taken_at: datetime
    media_items: list[MediaItem]
    caption: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileInfo:
    username: str
    full_name: str
    biography: str
    followers: int
    followees: int
    media_count: int
    profile_pic_url: str
