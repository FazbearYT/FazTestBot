"""Durable, non-secret process status for deployment health probes."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.paths import DATA_DIR
from core.process_lock import (
    APPLICATION_LOCK_PATH,
    ApplicationAlreadyRunningError,
    ApplicationLock,
)

RUNTIME_STATUS_PATH = DATA_DIR / "runtime-status.json"


@dataclass(frozen=True, slots=True)
class LivenessResult:
    live: bool
    summary: str
    details: dict[str, Any]


class RuntimeStatus:
    """Publish readiness while the polling process owns the application lock."""

    def __init__(
        self,
        version: str,
        loaded_module_count: int,
        *,
        path: str | Path = RUNTIME_STATUS_PATH,
        pid: int | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.version = version
        self.loaded_module_count = loaded_module_count
        self.pid = os.getpid() if pid is None else pid
        self._now = now or (lambda: datetime.now(timezone.utc))

    def __enter__(self) -> RuntimeStatus:
        self.publish()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.clear()

    def publish(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{self.pid}.tmp")
        payload = {
            "state": "ready",
            "pid": self.pid,
            "version": self.version,
            "loaded_module_count": self.loaded_module_count,
            "started_at": self._now().isoformat().replace("+00:00", "Z"),
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def probe_liveness(
    *,
    status_path: str | Path = RUNTIME_STATUS_PATH,
    lock_path: str | Path = APPLICATION_LOCK_PATH,
    lock_factory: Callable[[str | Path], ApplicationLock] = ApplicationLock,
) -> LivenessResult:
    """Confirm that a valid ready marker is protected by the live process lock."""

    path = Path(status_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return LivenessResult(False, "runtime status is absent", {})
    except (OSError, json.JSONDecodeError):
        return LivenessResult(False, "runtime status is unreadable", {})

    required = {"state", "pid", "version", "loaded_module_count", "started_at"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        return LivenessResult(False, "runtime status is invalid", {})
    if payload["state"] != "ready" or not isinstance(payload["pid"], int):
        return LivenessResult(False, "runtime is not ready", {})

    lock = lock_factory(lock_path)
    try:
        lock.acquire()
    except ApplicationAlreadyRunningError:
        return LivenessResult(
            True,
            "polling process owns the application lock",
            {
                "pid": payload["pid"],
                "version": payload["version"],
                "loaded_module_count": payload["loaded_module_count"],
                "started_at": payload["started_at"],
            },
        )
    else:
        lock.release()
        return LivenessResult(False, "runtime status is stale", {"pid": payload["pid"]})


__all__ = [
    "LivenessResult",
    "RUNTIME_STATUS_PATH",
    "RuntimeStatus",
    "probe_liveness",
]
