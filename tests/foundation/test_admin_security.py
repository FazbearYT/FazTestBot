import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path

from core.admin import AdminManager


class AdminSecurityTests(unittest.TestCase):
    def test_empty_legacy_code_disables_code_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(Path(directory) / "admin.db", secret_code="")
            authenticated = manager.authenticate_by_code(123, "")

        self.assertFalse(authenticated)
        self.assertNotIn(123, manager.admin_sessions)

    def test_standalone_manager_migrates_schema_and_supports_admin_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(Path(directory) / "admin.db", admins=())
            operation_id = str(uuid.uuid4())
            with manager.database.connection(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO users (user_id, username, full_name, module_stats)
                    VALUES (?, ?, ?, ?)
                    """,
                    (123, "fazbear", "Faz Bear", '{"cipher": 1}'),
                )
                connection.execute(
                    """
                    INSERT INTO cipher_operations (
                        operation_id, user_id, cipher_type, original_text,
                        encrypted_text, language, step, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        123,
                        "caesar",
                        "hello",
                        "khoor",
                        "en",
                        3,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )

            manager.log_admin_action(999, "inspect", 123, "x" * 600)

            stats = manager.get_global_stats()
            profile = manager.get_user_profile(123)
            operations = manager.search_operations("hello")
            with manager.database.connection() as connection:
                admin_log = connection.execute(
                    "SELECT admin_id, action, target_user_id, details FROM admin_logs"
                ).fetchone()

        self.assertEqual(1, stats["total_users"])
        self.assertEqual(1, stats["total_operations"])
        self.assertEqual({"caesar": 1}, stats["cipher_distribution"])
        self.assertEqual("fazbear", profile["username"])
        self.assertEqual(operation_id, operations[0]["operation_id"])
        self.assertEqual((999, "inspect", 123), tuple(admin_log[:3]))
        self.assertEqual(500, len(admin_log[3]))

    def test_emergency_clear_is_rolled_back_when_user_delete_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(Path(directory) / "admin.db")
            with manager.database.connection(write=True) as connection:
                connection.execute("INSERT INTO users (user_id) VALUES (123)")
                connection.execute(
                    """
                    INSERT INTO cipher_operations (
                        operation_id, user_id, cipher_type, original_text, encrypted_text
                    ) VALUES ('operation', 123, 'caesar', 'hello', 'khoor')
                    """
                )
                connection.execute(
                    """
                    CREATE TRIGGER reject_user_delete
                    BEFORE DELETE ON users
                    BEGIN
                        SELECT RAISE(ABORT, 'delete rejected');
                    END
                    """
                )

            with self.assertRaises(Exception):
                manager.emergency_clear_all()

            with manager.database.connection() as connection:
                users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                operations = connection.execute(
                    "SELECT COUNT(*) FROM cipher_operations"
                ).fetchone()[0]

        self.assertEqual(1, users)
        self.assertEqual(1, operations)
