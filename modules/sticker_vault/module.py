"""FazTestBot integration layer for Sticker Vault."""

from __future__ import annotations

import logging
from html import escape
from io import BytesIO
from typing import Any

from telebot import types

import config
from core.database import DatabaseManager
from core.keyboards import back_to_modules_keyboard
from core.module_base import BaseModule

from .config import (
    CALLBACK_PREFIX,
    MODULE_VERSION,
    PENDING_ACTION_CACHE_SIZE,
    PENDING_ACTION_TTL_SECONDS,
    SUPPORTED_STICKER_TYPES,
)
from .keyboards import result_keyboard, sticker_actions_keyboard, vault_menu_keyboard
from .models import AddStatus, PendingLookupStatus, PendingSticker
from .pending import PendingStickerStore
from .repository import StickerVaultRepository
from .service import StickerVaultError, StickerVaultService

logger = logging.getLogger(__name__)


class StickerVaultModule(BaseModule):
    def __init__(
        self,
        repository: StickerVaultRepository | None = None,
        user_database: DatabaseManager | None = None,
        pending_store: PendingStickerStore | None = None,
    ):
        super().__init__(
            module_id="sticker_vault",
            name="Sticker Vault",
            description="Собирает присланные стикеры в ваш личный набор",
            icon="🗃️",
            version=MODULE_VERSION,
            callback_prefix=CALLBACK_PREFIX,
        )
        self.repository = repository
        self.user_database = user_database
        self.pending_store = pending_store or PendingStickerStore(
            ttl_seconds=PENDING_ACTION_TTL_SECONDS,
            max_size=PENDING_ACTION_CACHE_SIZE,
        )
        self.service: StickerVaultService | None = None

    def on_load(self, bot: Any) -> None:
        self._ensure_storage()
        self.service = StickerVaultService(bot, self.repository)
        bot.register_message_handler(
            self._handle_sticker_message,
            content_types=["sticker"],
            pass_bot=True,
        )

    def handle_entry(self, bot: Any, call: Any) -> None:
        if not self._is_private_call(call):
            self._show_private_only(bot, call)
            return
        self._ensure_storage()
        self._show_menu(
            bot, call.message.chat.id, call.message.message_id, call.from_user.id
        )

    def handle_callback(self, bot: Any, call: Any) -> None:
        self._ensure_storage()
        if call.data == "sv_refresh":
            if not self._is_private_call(call):
                self._show_private_only(bot, call)
                return
            self._show_menu(
                bot, call.message.chat.id, call.message.message_id, call.from_user.id
            )
            return

        action, token = self._parse_action(call.data)
        if action is None:
            self._safe_edit(
                bot,
                call,
                "⚠️ Действие не распознано. Отправьте стикер ещё раз.",
                back_to_modules_keyboard(),
            )
            return

        lookup = self.pending_store.take(token, call.from_user.id)
        if lookup.status is PendingLookupStatus.FORBIDDEN:
            self._safe_edit(
                bot, call, "⚠️ Это действие принадлежит другому пользователю."
            )
            return
        if lookup.status is PendingLookupStatus.MISSING or lookup.sticker is None:
            self._safe_edit(
                bot,
                call,
                "⌛ Действие устарело или уже выполнено. Отправьте стикер ещё раз.",
            )
            return

        sticker = lookup.sticker
        if call.message.chat.id != sticker.chat_id:
            self._safe_edit(
                bot, call, "⚠️ Это действие доступно только в исходном чате."
            )
            return

        if action == "cancel":
            self._safe_edit(bot, call, "✖️ Действие отменено.")
        elif action == "file":
            self._download_sticker(bot, call, sticker)
        elif action == "add":
            self._add_sticker(bot, call, sticker)

    def get_menu_keyboard(self) -> types.InlineKeyboardMarkup:
        return vault_menu_keyboard([])

    def _handle_sticker_message(self, message: Any, bot: Any) -> None:
        if message.from_user.id in config.BLOCKED_USERS:
            return

        self._ensure_storage()
        self.user_database.create_or_update_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        if message.chat.type != "private":
            bot.reply_to(
                message, "Sticker Vault работает только в личном чате с ботом."
            )
            return

        source = message.sticker
        if getattr(source, "type", "regular") not in SUPPORTED_STICKER_TYPES:
            bot.reply_to(
                message,
                "Пока можно сохранять только обычные стикеры — без масок и custom emoji.",
            )
            return

        sticker = PendingSticker(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            file_id=source.file_id,
            file_unique_id=source.file_unique_id,
            sticker_format=self._sticker_format(source),
            emoji=source.emoji or "",
        )
        token = self.pending_store.put(sticker)
        bot.reply_to(
            message,
            "Что сделать с этим стикером?",
            reply_markup=sticker_actions_keyboard(token),
        )

    def _show_menu(
        self,
        bot: Any,
        chat_id: int,
        message_id: int,
        user_id: int,
    ) -> None:
        self._ensure_storage()
        records = self.repository.list_packs(user_id)
        if records:
            text = (
                "🗃️ <b>Sticker Vault</b>\n\n"
                "Отправьте мне обычный стикер отдельным сообщением. "
                "Статические, анимированные и видеостикеры сохраняются в одном наборе.\n\n"
                f"Ваших частей набора: <b>{len(records)}</b>"
            )
        else:
            text = (
                "🗃️ <b>Sticker Vault</b>\n\n"
                "Отправьте мне обычный стикер отдельным сообщением — я предложу "
                "добавить его в ваш персональный набор или скачать исходный файл.\n\n"
                "Поддерживаются статические, анимированные и видеостикеры в одном наборе."
            )
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=vault_menu_keyboard([record.pack_name for record in records]),
            parse_mode="HTML",
        )

    def _add_sticker(self, bot: Any, call: Any, sticker: PendingSticker) -> None:
        self._ensure_storage()
        if self.service is None:
            self.service = StickerVaultService(bot, self.repository)
        display_name = " ".join(
            part
            for part in (call.from_user.first_name, call.from_user.last_name)
            if part
        )
        try:
            result = self.service.add(sticker, display_name)
        except StickerVaultError as exc:
            self._safe_edit(
                bot,
                call,
                f"⚠️ {escape(str(exc))}",
                self._retry_keyboard(sticker),
            )
            return
        except Exception:
            logger.exception("Unexpected Sticker Vault add failure")
            self._safe_edit(
                bot,
                call,
                "⚠️ Не удалось сохранить стикер. Попробуйте позже.",
                self._retry_keyboard(sticker),
            )
            return

        if result.status is AddStatus.DUPLICATE:
            text = "ℹ️ Этот стикер уже есть в вашем наборе."
        elif result.status is AddStatus.CREATED:
            text = "✅ Создан персональный набор, стикер добавлен."
        else:
            text = "✅ Стикер добавлен в ваш персональный набор."
        self._safe_edit(bot, call, text, result_keyboard(result.pack_name))

    def _download_sticker(self, bot: Any, call: Any, sticker: PendingSticker) -> None:
        extension = {"static": "webp", "animated": "tgs", "video": "webm"}[
            sticker.sticker_format
        ]
        filename = f"sticker_{sticker.file_unique_id[:16]}.{extension}"
        try:
            file_info = bot.get_file(sticker.file_id)
            payload = BytesIO(bot.download_file(file_info.file_path))
            payload.name = filename
            bot.send_document(
                chat_id=sticker.chat_id,
                document=payload,
                visible_file_name=filename,
            )
        except Exception:
            logger.exception("Unexpected Sticker Vault download failure")
            self._safe_edit(
                bot,
                call,
                "⚠️ Не удалось скачать файл стикера. Попробуйте позже.",
                self._retry_keyboard(sticker),
            )
            return
        self._safe_edit(
            bot, call, f"📥 Файл отправлен: <code>{escape(filename)}</code>"
        )

    def _ensure_storage(self) -> None:
        if self.repository is None:
            self.repository = StickerVaultRepository(config.DATABASE_PATH)
        if self.user_database is None:
            self.user_database = DatabaseManager()

    def _retry_keyboard(self, sticker: PendingSticker) -> types.InlineKeyboardMarkup:
        return sticker_actions_keyboard(self.pending_store.put(sticker))

    @staticmethod
    def _is_private_call(call: Any) -> bool:
        return getattr(call.message.chat, "type", None) == "private"

    @staticmethod
    def _show_private_only(bot: Any, call: Any) -> None:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "🔒 <b>Sticker Vault доступен только в личном чате.</b>\n\n"
                "Откройте диалог с ботом и отправьте ему стикер."
            ),
            reply_markup=back_to_modules_keyboard(),
            parse_mode="HTML",
        )

    @staticmethod
    def _parse_action(callback_data: str) -> tuple[str | None, str]:
        for action in ("add", "file", "cancel"):
            prefix = f"sv_{action}_"
            if callback_data.startswith(prefix):
                token = callback_data[len(prefix) :]
                if token:
                    return action, token
        return None, ""

    @staticmethod
    def _sticker_format(sticker: Any) -> str:
        if getattr(sticker, "is_video", False):
            return "video"
        if getattr(sticker, "is_animated", False):
            return "animated"
        return "static"

    @staticmethod
    def _safe_edit(
        bot: Any,
        call: Any,
        text: str,
        reply_markup: types.InlineKeyboardMarkup | None = None,
    ) -> None:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
