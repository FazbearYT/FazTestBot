"""Small value objects used by Sticker Vault."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class PendingSticker:
    user_id: int
    chat_id: int
    file_id: str
    file_unique_id: str
    sticker_format: str
    emoji: str


@dataclass(frozen=True)
class StickerPackRecord:
    user_id: int
    part_number: int
    pack_name: str
    last_known_count: int = 0


class AddStatus(str, Enum):
    CREATED = "created"
    ADDED = "added"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class AddResult:
    status: AddStatus
    pack_name: str
    part_number: int
    sticker_count: int


class PendingLookupStatus(str, Enum):
    FOUND = "found"
    MISSING = "missing"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class PendingLookup:
    status: PendingLookupStatus
    sticker: PendingSticker | None = None
