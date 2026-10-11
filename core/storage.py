"""Shared SQLite connection and snapshot primitives."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path


class DatabaseIntegrityError(RuntimeError):
    """Raised when SQLite reports a damaged or invalid database."""


class SQLiteDatabase:
    """Create consistently configured, short-lived SQLite connections."""

    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5_000):
        if busy_timeout_ms < 1:
            raise ValueError("busy_timeout_ms must be positive")
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        if read_only:
            uri = f"{self.path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=self.busy_timeout_ms / 1_000,
            )
        else:
            connection = sqlite3.connect(
                self.path,
                timeout=self.busy_timeout_ms / 1_000,
            )

        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
            if not read_only:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = NORMAL")
        except Exception:
            connection.close()
            raise
        return connection

    @contextmanager
    def connection(
        self,
        *,
        write: bool = False,
        read_only: bool = False,
    ) -> Iterator[sqlite3.Connection]:
        if write and read_only:
            raise ValueError("a connection cannot be both writable and read-only")
        connection = self.connect(read_only=read_only)
        try:
            yield connection
            if write:
                connection.commit()
        except Exception:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def check_integrity(connection: sqlite3.Connection) -> None:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            detail = result[0] if result else "no result"
            raise DatabaseIntegrityError(f"SQLite integrity check failed: {detail}")

    def validate(self) -> None:
        with self.connection(read_only=True) as connection:
            self.check_integrity(connection)

    def backup_to(self, destination: str | Path) -> Path:
        """Create and verify a consistent snapshot, then publish it atomically."""

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)

        try:
            with (
                self.connection(read_only=True) as source,
                closing(sqlite3.connect(temporary_path)) as target,
            ):
                source.backup(target)
                self.check_integrity(target)
            os.replace(temporary_path, destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return destination

    def restore_from(self, source: str | Path) -> None:
        """Validate and atomically restore through SQLite's Online Backup API."""

        source_database = SQLiteDatabase(source, busy_timeout_ms=self.busy_timeout_ms)
        with source_database.connection(read_only=True) as source_connection:
            self.check_integrity(source_connection)
            with self.connection() as target_connection:
                source_connection.backup(target_connection)
                self.check_integrity(target_connection)
