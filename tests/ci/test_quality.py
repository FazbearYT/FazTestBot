import unittest

from scripts.ci.quality import FORMAT_TARGETS, LINT_TARGETS


class QualityTargetsTests(unittest.TestCase):
    def test_admin_runtime_is_covered_by_lint(self):
        self.assertIn("core/admin.py", LINT_TARGETS)
        self.assertIn("core/admin_panel.py", LINT_TARGETS)
        self.assertIn("core/admin_security.py", LINT_TARGETS)
        self.assertIn("core/handlers.py", LINT_TARGETS)
        self.assertIn("core/keyboards.py", LINT_TARGETS)

    def test_only_explicit_legacy_handler_is_exempt_from_formatting(self):
        self.assertEqual({"core/handlers.py"}, set(LINT_TARGETS) - set(FORMAT_TARGETS))


if __name__ == "__main__":
    unittest.main()
