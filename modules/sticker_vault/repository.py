"""SQLite persistence for the sticker packs created for each user."""

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from .config import PACK_TABLE
from .models import StickerPackRecord


class StickerVaultRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _init_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {PACK_TABLE} (
                    user_id INTEGER NOT NULL,
                    part_number INTEGER NOT NULL CHECK(part_number > 0),
                    pack_name TEXT NOT NULL UNIQUE,
                    last_known_count INTEGER NOT NULL DEFAULT 0 CHECK(last_known_count >= 0),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, part_number)
                )
                """
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{PACK_TABLE}_user ON {PACK_TABLE}(user_id)"
            )
            connection.commit()

    def list_packs(self, user_id: int) -> list[StickerPackRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT user_id, part_number, pack_name, last_known_count
                FROM {PACK_TABLE}
                WHERE user_id = ?
                ORDER BY part_number
                """,
                (user_id,),
            ).fetchall()
        return [self._to_record(row) for row in rows]

    def upsert_pack(self, record: StickerPackRecord) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                f"""
                INSERT INTO {PACK_TABLE} (user_id, part_number, pack_name, last_known_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, part_number) DO UPDATE SET
                    pack_name = excluded.pack_name,
                    last_known_count = excluded.last_known_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    record.user_id,
                    record.part_number,
                    record.pack_name,
                    record.last_known_count,
                ),
            )
            connection.commit()

    def remove_pack(self, user_id: int, part_number: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                f"DELETE FROM {PACK_TABLE} WHERE user_id = ? AND part_number = ?",
                (user_id, part_number),
            )
            connection.commit()

    def replace_user_packs(self, user_id: int, records: Iterable[StickerPackRecord]) -> None:
        records = list(records)
        with closing(self._connect()) as connection:
            connection.execute(f"DELETE FROM {PACK_TABLE} WHERE user_id = ?", (user_id,))
            connection.executemany(
                f"""
                INSERT INTO {PACK_TABLE} (user_id, part_number, pack_name, last_known_count)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        record.user_id,
                        record.part_number,
                        record.pack_name,
                        record.last_known_count,
                    )
                    for record in records
                ],
            )
            connection.commit()

    @staticmethod
    def _to_record(row: sqlite3.Row) -> StickerPackRecord:
        return StickerPackRecord(
            user_id=row["user_id"],
            part_number=row["part_number"],
            pack_name=row["pack_name"],
            last_known_count=row["last_known_count"],
        )
