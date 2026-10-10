import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from core.admin import AdminManager
from core.admin_security import (
    AdminConfirmationStore,
    AdminInteractionState,
    has_admin_access,
    is_private_chat,
)


def update(user_id=1, chat_id=10, chat_type="private", *, callback=False):
    message = SimpleNamespace(chat=SimpleNamespace(id=chat_id, type=chat_type))
    base = SimpleNamespace(from_user=SimpleNamespace(id=user_id), chat=message.chat)
    if callback:
        return SimpleNamespace(from_user=base.from_user, message=message)
    return base


class AdminInteractionTests(unittest.TestCase):
    def test_access_requires_private_chat_and_current_admin_status(self):
        manager = SimpleNamespace(is_admin=lambda user_id: user_id == 1)

        self.assertTrue(has_admin_access(update(), manager))
        self.assertTrue(has_admin_access(update(callback=True), manager))
        self.assertFalse(has_admin_access(update(chat_type="group"), manager))
        self.assertFalse(has_admin_access(update(user_id=2), manager))

    def test_private_chat_detection_handles_missing_shapes(self):
        self.assertFalse(is_private_chat(SimpleNamespace()))

    def test_input_state_is_chat_bound_single_use_and_expires(self):
        current = datetime(2026, 1, 1, 12, 0)
        state = AdminInteractionState(ttl_seconds=60, now=lambda: current)
        state.begin(1, 10, "search_user", 50)

        self.assertIsNone(state.consume(1, 11, "search_user"))
        self.assertIsNone(state.consume(1, 10, "search_logs"))
        self.assertIsNotNone(state.consume(1, 10, "search_user"))
        self.assertIsNone(state.consume(1, 10, "search_user"))

        state.begin(1, 10, "search_user", 50)
        current += timedelta(seconds=60)
        self.assertIsNone(state.peek(1, 10))

    def test_authentication_uses_injected_policy_and_session_can_be_revoked(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(
                Path(directory) / "users.db",
                admins=(100,),
                secret_code="correct",
                session_hours=1,
            )

            self.assertTrue(manager.is_admin(100))
            self.assertFalse(manager.authenticate_by_code(200, "неверный код"))
            self.assertFalse(manager.authenticate_by_code(200, "wrong"))
            self.assertTrue(manager.authenticate_by_code(200, "correct"))
            self.assertTrue(manager.is_admin(200))
            self.assertTrue(manager.revoke_session(200))
            self.assertFalse(manager.is_admin(200))
            self.assertFalse(manager.revoke_session(200))

    def test_authentication_throttles_failures_until_lockout_expires(self):
        current = datetime(2026, 1, 1, 12, 0)
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(
                Path(directory) / "users.db",
                admins=(),
                secret_code="correct",
                auth_max_failures=2,
                auth_window_minutes=10,
                auth_lockout_minutes=5,
                now=lambda: current,
            )

            self.assertFalse(manager.authenticate_by_code(200, "wrong"))
            self.assertFalse(manager.authenticate_by_code(200, "wrong"))
            self.assertFalse(manager.authenticate_by_code(200, "correct"))
            current += timedelta(minutes=5)
            self.assertTrue(manager.authenticate_by_code(200, "correct"))

    def test_destructive_confirmation_is_actor_bound_single_use_and_expires(self):
        current = datetime(2026, 1, 1, 12, 0)
        tokens = iter(("first-token", "second-token"))
        confirmations = AdminConfirmationStore(
            ttl_seconds=60,
            now=lambda: current,
            token_factory=lambda: next(tokens),
        )
        token = confirmations.issue(1, 10, "cleanup_logs", "30")

        self.assertIsNone(confirmations.consume(token, 2, 10))
        self.assertIsNone(confirmations.consume(token, 1, 11))
        confirmed = confirmations.consume(token, 1, 10)
        self.assertEqual(("cleanup_logs", "30"), (confirmed.action, confirmed.payload))
        self.assertIsNone(confirmations.consume(token, 1, 10))

        token = confirmations.issue(1, 10, "emergency_clear")
        current += timedelta(seconds=60)
        self.assertIsNone(confirmations.consume(token, 1, 10))

    def test_new_confirmation_revokes_previous_token_for_actor(self):
        tokens = iter(("first-token", "second-token"))
        confirmations = AdminConfirmationStore(token_factory=lambda: next(tokens))
        first = confirmations.issue(1, 10, "cleanup_logs", "7")
        second = confirmations.issue(1, 10, "cleanup_logs", "30")

        self.assertIsNone(confirmations.consume(first, 1, 10))
        self.assertIsNotNone(confirmations.consume(second, 1, 10))

    def test_auth_failure_tracking_is_bounded_and_thread_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(
                Path(directory) / "users.db",
                admins=(),
                secret_code="correct",
                auth_max_failures=100,
                auth_failure_capacity=2,
            )
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(
                    executor.map(
                        lambda _index: manager.authenticate_by_code(1, "wrong"),
                        range(20),
                    )
                )
            manager.authenticate_by_code(2, "wrong")
            manager.authenticate_by_code(3, "wrong")

        self.assertEqual([False] * 20, results)
        self.assertLessEqual(len(manager._auth_failures), 2)


if __name__ == "__main__":
    unittest.main()
