"""Cross-platform process lock protecting the live application database."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

from core.paths import TEMP_DIR

APPLICATION_LOCK_PATH = TEMP_DIR / "faztestbot.lock"


class ApplicationAlreadyRunningError(RuntimeError):
    """Raised when another process owns the application lock."""


class ApplicationLock:
    """Non-blocking exclusive lock retained for the lifetime of a process."""

    def __init__(self, path: str | Path = APPLICATION_LOCK_PATH):
        self.path = Path(path)
        self._file: BinaryIO | None = None

    def acquire(self) -> None:
        if self._file is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.open("a+b")
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            self._lock(lock_file)
        except OSError as error:
            lock_file.close()
            raise ApplicationAlreadyRunningError(
                "another FazTestBot process is using the application lock"
            ) from error
        self._file = lock_file

    def release(self) -> None:
        lock_file = self._file
        if lock_file is None:
            return
        self._file = None
        try:
            self._unlock(lock_file)
        finally:
            lock_file.close()

    @staticmethod
    def _lock(lock_file: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(lock_file: BinaryIO) -> None:
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def __enter__(self) -> ApplicationLock:
        self.acquire()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


__all__ = ["APPLICATION_LOCK_PATH", "ApplicationAlreadyRunningError", "ApplicationLock"]
