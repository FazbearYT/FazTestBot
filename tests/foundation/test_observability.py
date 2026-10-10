import json
import logging
import tempfile
import unittest
from pathlib import Path

from core.observability import (
    LOG_FILENAME,
    configure_logging,
    event_fields,
    get_logger,
    operation_context,
    redact,
)


class ObservabilityTests(unittest.TestCase):
    def tearDown(self):
        logger = get_logger()
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_json_log_contains_event_and_operation_context(self):
        with tempfile.TemporaryDirectory() as directory:
            configure_logging(log_dir=directory, console=False)
            with operation_context("operation-123"):
                get_logger("tests").info(
                    "backup completed",
                    extra=event_fields("backup.completed", backup_type="manual"),
                )
            for handler in get_logger().handlers:
                handler.flush()

            payload = json.loads((Path(directory) / LOG_FILENAME).read_text(encoding="utf-8"))
            self._close_handlers()

        self.assertEqual("backup.completed", payload["event"])
        self.assertEqual("manual", payload["backup_type"])
        self.assertEqual("operation-123", payload["operation_id"])
        self.assertEqual("faztestbot.tests", payload["logger"])

    def test_known_secret_forms_are_redacted(self):
        token = "123456789:" + "A" * 35

        self.assertNotIn(token, redact(f"request failed for {token}"))
        self.assertEqual("BOT_TOKEN=[REDACTED]", redact(f"BOT_TOKEN={token}"))
        self.assertEqual("api_key: [REDACTED]", redact("api_key: very-secret"))

    def test_reconfiguration_replaces_owned_handlers(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = configure_logging(log_dir=directory, console=True)
            self.assertEqual(2, len(logger.handlers))

            configured_again = configure_logging(log_dir=directory, console=False)

        self.assertIs(logger, configured_again)
        self.assertEqual(1, len(logger.handlers))

    def test_event_fields_reject_log_record_attribute_collisions(self):
        with self.assertRaisesRegex(ValueError, "filename"):
            event_fields("backup.created", filename="snapshot.db")

    def test_logger_namespace_propagates_to_application_handlers(self):
        with tempfile.TemporaryDirectory() as directory:
            configure_logging(log_dir=directory, console=False)
            child = get_logger("core.database")

            self.assertEqual("faztestbot.core.database", child.name)
            self.assertTrue(child.propagate)
            self.assertEqual(logging.INFO, get_logger().level)

    @staticmethod
    def _close_handlers():
        logger = get_logger()
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    unittest.main()
