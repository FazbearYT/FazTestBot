"""Process-signal lifecycle helpers for service-style execution."""

from __future__ import annotations

import signal
from collections.abc import Callable
from types import FrameType
from typing import Any


class ShutdownSignalHandlers:
    """Temporarily translate termination signals into one shutdown request."""

    def __init__(self, request_shutdown: Callable[[], Any]) -> None:
        self._request_shutdown = request_shutdown
        self._previous: dict[signal.Signals, Any] = {}
        self.received: signal.Signals | None = None

    def __enter__(self) -> ShutdownSignalHandlers:
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._previous[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle)
        return self

    def __exit__(self, *_exc_info: object) -> None:
        for signum, previous in self._previous.items():
            signal.signal(signum, previous)
        self._previous.clear()

    def _handle(self, signum: int, _frame: FrameType | None) -> None:
        received = signal.Signals(signum)
        if self.received is not None:
            return
        self.received = received
        self._request_shutdown()


__all__ = ["ShutdownSignalHandlers"]
