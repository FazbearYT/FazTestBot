"""Private-chat authorization and bounded state for admin interactions."""

from __future__ import annotations

import base64
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


def _new_token() -> str:
    return base64.urlsafe_b64encode(os.urandom(12)).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class AdminInputState:
    mode: str
    message_id: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AdminConfirmation:
    action: str
    payload: str
    user_id: int
    chat_id: int
    expires_at: datetime


class AdminInteractionState:
    """Short-lived state bound to one administrator and one private chat."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 300,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.ttl = timedelta(seconds=ttl_seconds)
        self.now = now
        self._states: dict[tuple[int, int], AdminInputState] = {}

    def begin(self, user_id: int, chat_id: int, mode: str, message_id: int) -> None:
        self._states[(user_id, chat_id)] = AdminInputState(
            mode=mode,
            message_id=message_id,
            expires_at=self.now() + self.ttl,
        )

    def peek(self, user_id: int, chat_id: int) -> AdminInputState | None:
        key = (user_id, chat_id)
        state = self._states.get(key)
        if state is not None and self.now() >= state.expires_at:
            self._states.pop(key, None)
            return None
        return state

    def consume(self, user_id: int, chat_id: int, mode: str) -> AdminInputState | None:
        state = self.peek(user_id, chat_id)
        if state is None or state.mode != mode:
            return None
        self._states.pop((user_id, chat_id), None)
        return state

    def clear(self, user_id: int, chat_id: int | None = None) -> None:
        if chat_id is not None:
            self._states.pop((user_id, chat_id), None)
            return
        for key in [key for key in self._states if key[0] == user_id]:
            self._states.pop(key, None)


class AdminConfirmationStore:
    """Issue short-lived, actor-bound tokens for destructive admin actions."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 120,
        now: Callable[[], datetime] = datetime.now,
        token_factory: Callable[[], str] = _new_token,
    ):
        self.ttl = timedelta(seconds=ttl_seconds)
        self.now = now
        self.token_factory = token_factory
        self._confirmations: dict[str, AdminConfirmation] = {}

    def issue(self, user_id: int, chat_id: int, action: str, payload: str = "") -> str:
        self._discard_expired()
        self.clear(user_id)
        token = self.token_factory()
        if not token or token in self._confirmations:
            raise RuntimeError("confirmation token factory returned an invalid token")
        self._confirmations[token] = AdminConfirmation(
            action=action,
            payload=payload,
            user_id=user_id,
            chat_id=chat_id,
            expires_at=self.now() + self.ttl,
        )
        return token

    def consume(self, token: str, user_id: int, chat_id: int) -> AdminConfirmation | None:
        confirmation = self._confirmations.get(token)
        if confirmation is None:
            return None
        if self.now() >= confirmation.expires_at:
            self._confirmations.pop(token, None)
            return None
        if confirmation.user_id != user_id or confirmation.chat_id != chat_id:
            return None
        return self._confirmations.pop(token)

    def clear(self, user_id: int) -> None:
        for token, confirmation in list(self._confirmations.items()):
            if confirmation.user_id == user_id:
                self._confirmations.pop(token, None)

    def _discard_expired(self) -> None:
        now = self.now()
        for token, confirmation in list(self._confirmations.items()):
            if now >= confirmation.expires_at:
                self._confirmations.pop(token, None)


def is_private_chat(update: Any) -> bool:
    """Return whether a Telegram message or callback belongs to a private chat."""

    message = getattr(update, "message", update)
    chat = getattr(message, "chat", None)
    return getattr(chat, "type", None) == "private"


def has_admin_access(update: Any, admin_manager: Any) -> bool:
    """Require both a private chat and a currently valid admin session."""

    actor = getattr(update, "from_user", None)
    return bool(is_private_chat(update) and actor is not None and admin_manager.is_admin(actor.id))


__all__ = [
    "AdminConfirmation",
    "AdminConfirmationStore",
    "AdminInputState",
    "AdminInteractionState",
    "has_admin_access",
    "is_private_chat",
]
