import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.admin import AdminManager


class AdminSecurityTests(unittest.TestCase):
    def test_empty_legacy_code_disables_code_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = AdminManager(Path(directory) / "admin.db")
            with patch("core.admin.ADMIN_SECRET_CODE", ""):
                authenticated = manager.authenticate_by_code(123, "")

        self.assertFalse(authenticated)
        self.assertNotIn(123, manager.admin_sessions)
