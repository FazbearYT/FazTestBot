"""Bounded, expiring storage for sticker action callbacks."""

import base64
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from .models import PendingLookup, PendingLookupStatus, PendingSticker


@dataclass(frozen=True)
class _Entry:
    sticker: PendingSticker
    expires_at: float


class PendingStickerStore:
    def __init__(
        self,
        ttl_seconds: int,
        max_size: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_size <= 0:
            raise ValueError("max_size must be positive")

        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._clock = clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.RLock()

    def put(self, sticker: PendingSticker) -> str:
        with self._lock:
            self._remove_expired()
            while len(self._entries) >= self._max_size:
                self._entries.popitem(last=False)

            token = self._new_token()
            self._entries[token] = _Entry(
                sticker=sticker,
                expires_at=self._clock() + self._ttl_seconds,
            )
            return token

    def take(self, token: str, user_id: int) -> PendingLookup:
        with self._lock:
            self._remove_expired()
            entry = self._entries.get(token)
            if entry is None:
                return PendingLookup(PendingLookupStatus.MISSING)
            if entry.sticker.user_id != user_id:
                return PendingLookup(PendingLookupStatus.FORBIDDEN)

            del self._entries[token]
            return PendingLookup(PendingLookupStatus.FOUND, entry.sticker)

    def _new_token(self) -> str:
        token = self._random_token()
        while token in self._entries:
            token = self._random_token()
        return token

    @staticmethod
    def _random_token() -> str:
        return base64.urlsafe_b64encode(os.urandom(9)).decode("ascii").rstrip("=")

    def _remove_expired(self) -> None:
        now = self._clock()
        expired = [token for token, entry in self._entries.items() if entry.expires_at <= now]
        for token in expired:
            del self._entries[token]
