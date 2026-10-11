"""Thread-safe bounded storage for short-lived interaction state."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class InteractionScope:
    """Identify one Telegram actor inside one chat."""

    actor_id: int
    chat_id: int


@dataclass(slots=True)
class _StateRecord:
    values: dict[str, Any] = field(default_factory=dict)
    touched_at: float = 0.0


class TransientStateStore:
    """Keep bounded interaction state with sliding expiration."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 3_600,
        max_entries: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ):
        if ttl_seconds <= 0:
            raise ValueError("state TTL must be positive")
        if max_entries <= 0:
            raise ValueError("state entry limit must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._records: dict[InteractionScope, _StateRecord] = {}
        self._lock = RLock()

    def get(self, scope: InteractionScope, key: str, default: Any = None) -> Any:
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            record = self._records.get(scope)
            if record is None:
                return default
            record.touched_at = now
            return record.values.get(key, default)

    def get_all(self, scope: InteractionScope) -> dict[str, Any]:
        """Return a shallow copy so callers cannot mutate storage outside the lock."""

        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            record = self._records.get(scope)
            if record is None:
                return {}
            record.touched_at = now
            return dict(record.values)

    def set(self, scope: InteractionScope, key: str, value: Any) -> None:
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            record = self._records.get(scope)
            if record is None:
                self._make_room()
                record = _StateRecord(touched_at=now)
                self._records[scope] = record
            record.values[key] = value
            record.touched_at = now

    def clear(self, scope: InteractionScope) -> bool:
        with self._lock:
            return self._records.pop(scope, None) is not None

    def count(self) -> int:
        with self._lock:
            self._prune_expired(self._clock())
            return len(self._records)

    def _prune_expired(self, now: float) -> None:
        expired = [
            scope
            for scope, record in self._records.items()
            if now - record.touched_at >= self.ttl_seconds
        ]
        for scope in expired:
            del self._records[scope]

    def _make_room(self) -> None:
        if len(self._records) < self.max_entries:
            return
        oldest_scope = min(self._records, key=lambda scope: self._records[scope].touched_at)
        del self._records[oldest_scope]


__all__ = ["InteractionScope", "TransientStateStore"]
