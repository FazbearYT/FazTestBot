"""Telegram-facing business logic for Sticker Vault."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any

from telebot import types
from telebot.apihelper import ApiTelegramException

from .config import (
    DEFAULT_STICKER_EMOJI,
    MAX_PACK_PARTS,
    PACK_CAPACITY,
    SUPPORTED_STICKER_FORMATS,
)
from .models import AddResult, AddStatus, PendingSticker, StickerPackRecord
from .repository import StickerVaultRepository

logger = logging.getLogger(__name__)


class StickerVaultError(RuntimeError):
    """A user-facing Sticker Vault operation failure."""


@dataclass(frozen=True)
class _RemotePack:
    record: StickerPackRecord
    sticker_set: Any


class StickerVaultService:
    def __init__(
        self,
        bot: Any,
        repository: StickerVaultRepository,
        bot_username: str | None = None,
    ):
        self.bot = bot
        self.repository = repository
        self._bot_username = self._normalize_bot_username(bot_username) if bot_username else None
        self._username_lock = threading.Lock()
        self._locks_guard = threading.Lock()
        self._user_locks: dict[int, threading.Lock] = {}

    def add(self, sticker: PendingSticker, user_display_name: str) -> AddResult:
        if sticker.sticker_format not in SUPPORTED_STICKER_FORMATS:
            raise StickerVaultError("Этот формат стикера пока не поддерживается.")

        lock = self._get_user_lock(sticker.user_id)
        with lock:
            return self._add_locked(sticker, user_display_name)

    def _add_locked(self, sticker: PendingSticker, user_display_name: str) -> AddResult:
        remote_packs = self._load_remote_packs(sticker.user_id)

        for remote in remote_packs:
            if self._contains_sticker(remote.sticker_set, sticker.file_unique_id):
                return AddResult(
                    status=AddStatus.DUPLICATE,
                    pack_name=remote.record.pack_name,
                    part_number=remote.record.part_number,
                    sticker_count=len(remote.sticker_set.stickers),
                )

        target = next(
            (
                remote
                for remote in reversed(remote_packs)
                if len(remote.sticker_set.stickers) < PACK_CAPACITY
            ),
            None,
        )
        input_sticker = self._to_input_sticker(sticker)

        if target is not None:
            emoji = sticker.emoji or DEFAULT_STICKER_EMOJI
            try:
                self.bot.add_sticker_to_set(
                    user_id=sticker.user_id,
                    name=target.record.pack_name,
                    # pyTelegramBotAPI keeps this legacy argument mandatory even
                    # when the modern InputSticker argument is supplied.
                    emojis=[emoji],
                    sticker=input_sticker,
                )
            except ApiTelegramException as exc:
                if self._is_pack_full(exc):
                    next_part = (
                        max(
                            (remote.record.part_number for remote in remote_packs),
                            default=0,
                        )
                        + 1
                    )
                    return self._create_pack(
                        sticker,
                        user_display_name,
                        input_sticker,
                        next_part,
                    )
                raise self._translate_api_error(exc) from exc

            count = len(target.sticker_set.stickers) + 1
            updated = StickerPackRecord(
                user_id=target.record.user_id,
                part_number=target.record.part_number,
                pack_name=target.record.pack_name,
                last_known_count=count,
            )
            self.repository.upsert_pack(updated)
            return AddResult(AddStatus.ADDED, updated.pack_name, updated.part_number, count)

        next_part = max((remote.record.part_number for remote in remote_packs), default=0) + 1
        return self._create_pack(sticker, user_display_name, input_sticker, next_part)

    def _create_pack(
        self,
        sticker: PendingSticker,
        user_display_name: str,
        input_sticker: types.InputSticker,
        next_part: int,
    ) -> AddResult:
        if next_part > MAX_PACK_PARTS:
            raise StickerVaultError("Достигнут предел количества частей стикерпака.")

        pack_name = self.build_pack_name(sticker.user_id, next_part)
        pack_title = self.build_pack_title(user_display_name, next_part)
        try:
            self.bot.create_new_sticker_set(
                user_id=sticker.user_id,
                name=pack_name,
                title=pack_title,
                stickers=[input_sticker],
                sticker_type="regular",
            )
        except ApiTelegramException as exc:
            if self._is_pack_name_occupied(exc):
                recovered = self._get_sticker_set(pack_name)
                if recovered is not None:
                    self.repository.upsert_pack(
                        StickerPackRecord(
                            user_id=sticker.user_id,
                            part_number=next_part,
                            pack_name=pack_name,
                            last_known_count=len(recovered.stickers),
                        )
                    )
                    if self._contains_sticker(recovered, sticker.file_unique_id):
                        return AddResult(
                            AddStatus.DUPLICATE,
                            pack_name,
                            next_part,
                            len(recovered.stickers),
                        )
                    if len(recovered.stickers) < PACK_CAPACITY:
                        emoji = sticker.emoji or DEFAULT_STICKER_EMOJI
                        try:
                            self.bot.add_sticker_to_set(
                                user_id=sticker.user_id,
                                name=pack_name,
                                emojis=[emoji],
                                sticker=input_sticker,
                            )
                        except ApiTelegramException as add_exc:
                            if self._is_pack_full(add_exc):
                                return self._create_pack(
                                    sticker,
                                    user_display_name,
                                    input_sticker,
                                    next_part + 1,
                                )
                            raise self._translate_api_error(add_exc) from add_exc
                        count = len(recovered.stickers) + 1
                        self.repository.upsert_pack(
                            StickerPackRecord(
                                sticker.user_id,
                                next_part,
                                pack_name,
                                count,
                            )
                        )
                        return AddResult(AddStatus.ADDED, pack_name, next_part, count)
                    return self._create_pack(
                        sticker,
                        user_display_name,
                        input_sticker,
                        next_part + 1,
                    )
            raise self._translate_api_error(exc) from exc

        record = StickerPackRecord(sticker.user_id, next_part, pack_name, 1)
        self.repository.upsert_pack(record)
        return AddResult(AddStatus.CREATED, pack_name, next_part, 1)

    def _load_remote_packs(self, user_id: int) -> list[_RemotePack]:
        records = self.repository.list_packs(user_id)
        records_by_part = {record.part_number: record for record in records}
        highest_recorded_part = max(records_by_part, default=0)
        remote_packs: list[_RemotePack] = []

        # Pack names are deterministic, so the Telegram state can rebuild a lost
        # or partially written local index. Probe until the first missing part
        # beyond the highest DB record; this also makes duplicate detection cover
        # every recovered part.
        part_number = 1
        while part_number <= MAX_PACK_PARTS:
            record = records_by_part.get(part_number) or StickerPackRecord(
                user_id,
                part_number,
                self.build_pack_name(user_id, part_number),
                0,
            )
            sticker_set = self._get_sticker_set(record.pack_name)
            if sticker_set is None:
                if part_number in records_by_part:
                    self.repository.remove_pack(user_id, part_number)
                if part_number > highest_recorded_part:
                    break
                part_number += 1
                continue
            refreshed = StickerPackRecord(
                user_id=user_id,
                part_number=record.part_number,
                pack_name=record.pack_name,
                last_known_count=len(sticker_set.stickers),
            )
            self.repository.upsert_pack(refreshed)
            remote_packs.append(_RemotePack(refreshed, sticker_set))
            part_number += 1

        return remote_packs

    def _get_sticker_set(self, pack_name: str) -> Any | None:
        try:
            return self.bot.get_sticker_set(pack_name)
        except ApiTelegramException as exc:
            if self._is_missing_pack(exc):
                return None
            raise self._translate_api_error(exc) from exc

    def build_pack_name(self, user_id: int, part_number: int) -> str:
        username = self._get_bot_username()
        name = f"sv_{user_id}_{part_number}_by_{username}"
        if len(name) > 64:
            raise StickerVaultError("Имя бота слишком длинное для создания стикерпака.")
        return name

    @staticmethod
    def build_pack_title(user_display_name: str, part_number: int) -> str:
        clean_name = " ".join((user_display_name or "User").split()) or "User"
        suffix = "" if part_number == 1 else f" · часть {part_number}"
        prefix = "Sticker Vault · "
        available = 64 - len(prefix) - len(suffix)
        return f"{prefix}{clean_name[:available]}{suffix}"

    def _get_bot_username(self) -> str:
        if self._bot_username:
            return self._bot_username
        with self._username_lock:
            if not self._bot_username:
                me = self.bot.get_me()
                self._bot_username = self._normalize_bot_username(me.username)
        return self._bot_username

    @staticmethod
    def _normalize_bot_username(username: str | None) -> str:
        normalized = (username or "").lstrip("@").lower()
        if not normalized or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,31}", normalized):
            raise StickerVaultError("Telegram не вернул корректное имя бота.")
        return normalized

    @staticmethod
    def _to_input_sticker(sticker: PendingSticker) -> types.InputSticker:
        emoji = sticker.emoji or DEFAULT_STICKER_EMOJI
        return types.InputSticker(
            sticker=sticker.file_id,
            emoji_list=[emoji],
            format=sticker.sticker_format,
        )

    @staticmethod
    def _contains_sticker(sticker_set: Any, file_unique_id: str) -> bool:
        return any(
            getattr(existing, "file_unique_id", None) == file_unique_id
            for existing in sticker_set.stickers
        )

    def _get_user_lock(self, user_id: int) -> threading.Lock:
        with self._locks_guard:
            return self._user_locks.setdefault(user_id, threading.Lock())

    @classmethod
    def _is_missing_pack(cls, exc: ApiTelegramException) -> bool:
        description = cls._api_description(exc)
        return "STICKERSET_INVALID" in description or "STICKERSET_NOT_FOUND" in description

    @classmethod
    def _is_pack_name_occupied(cls, exc: ApiTelegramException) -> bool:
        description = cls._api_description(exc)
        return "PACK_SHORT_NAME_OCCUPIED" in description or (
            "STICKER SET NAME" in description and "ALREADY OCCUPIED" in description
        )

    @classmethod
    def _is_pack_full(cls, exc: ApiTelegramException) -> bool:
        description = cls._api_description(exc)
        return "STICKERS_TOO_MUCH" in description or (
            "STICKER" in description and "TOO_MUCH" in description
        )

    @classmethod
    def _translate_api_error(cls, exc: ApiTelegramException) -> StickerVaultError:
        description = cls._api_description(exc)
        logger.warning("Telegram Sticker API error: %s", description)
        result_json = getattr(exc, "result_json", None) or {}
        if result_json.get("error_code") == 429:
            retry_after = (result_json.get("parameters") or {}).get("retry_after")
            if isinstance(retry_after, int) and retry_after > 0:
                return StickerVaultError(
                    f"Слишком много запросов к Telegram. Повторите через {retry_after} сек."
                )
            return StickerVaultError("Слишком много запросов к Telegram. Повторите немного позже.")
        if "USER_ID_INVALID" in description:
            return StickerVaultError("Сначала откройте личный чат с ботом и отправьте /start.")
        if "STICKER_EMOJI_INVALID" in description:
            return StickerVaultError("Telegram не принял emoji этого стикера.")
        if "STICKER" in description and "TOO_MUCH" in description:
            return StickerVaultError("Текущая часть стикерпака заполнена.")
        if "STICKER_FILE_INVALID" in description or "STICKER_INVALID" in description:
            return StickerVaultError("Telegram не принял файл стикера.")
        return StickerVaultError("Telegram не смог изменить стикерпак. Попробуйте позже.")

    @staticmethod
    def _api_description(exc: ApiTelegramException) -> str:
        result_json = getattr(exc, "result_json", None) or {}
        return str(result_json.get("description") or exc).upper()
