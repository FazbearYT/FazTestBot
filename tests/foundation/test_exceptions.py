import logging
import sqlite3
import unittest

from core.exceptions import (
    APIAuthenticationError,
    APIRateLimitError,
    DatabaseConnectionError,
    ErrorCategory,
    LimitExceededError,
    ValidationError,
    classify_exception,
    handle_exception,
    is_critical_error,
    is_system_error,
    is_user_error,
)


class ExceptionTaxonomyTests(unittest.TestCase):
    def test_subclasses_keep_their_specific_codes_and_metadata(self):
        database_error = DatabaseConnectionError("locked")
        validation_error = ValidationError("url", "invalid")

        self.assertEqual("DB_CONNECTION_ERROR", database_error.code)
        self.assertEqual("connect", database_error.operation)
        self.assertTrue(database_error.retryable)
        self.assertEqual("VALIDATION_ERROR", validation_error.code)
        self.assertEqual("url", validation_error.field)

    def test_categories_drive_retry_and_severity(self):
        rate_limit = classify_exception(APIRateLimitError("steam", retry_after=10))
        authentication = classify_exception(APIAuthenticationError("steam"))

        self.assertEqual(ErrorCategory.TRANSIENT, rate_limit.category)
        self.assertTrue(rate_limit.retryable)
        self.assertEqual(logging.WARNING, rate_limit.log_level)
        self.assertEqual(ErrorCategory.SYSTEM, authentication.category)
        self.assertFalse(authentication.retryable)

    def test_standard_exceptions_have_safe_messages(self):
        value_error = classify_exception(ValueError("private input contents"))
        sqlite_error = classify_exception(sqlite3.OperationalError("sensitive SQL"))

        self.assertNotIn("private input", value_error.user_message)
        self.assertNotIn("sensitive SQL", sqlite_error.user_message)
        self.assertEqual("SQLITE_ERROR", sqlite_error.code)

    def test_handler_logs_metadata_and_returns_safe_message(self):
        logger = logging.getLogger("test.exception-handler")
        error = DatabaseConnectionError("database path")

        with self.assertLogs(logger, logging.CRITICAL) as captured:
            message = handle_exception(
                error,
                logger,
                event="database.connection_failed",
                context={"component": "startup"},
            )

        self.assertEqual("❌ Ошибка базы данных. Попробуйте позже.", message)
        self.assertIn("DatabaseConnectionError", captured.output[0])

    def test_classification_helpers_are_consistent(self):
        user_error = LimitExceededError("requests", 10, current_value=0)
        critical_error = DatabaseConnectionError()

        self.assertTrue(is_user_error(user_error))
        self.assertFalse(is_system_error(user_error))
        self.assertTrue(is_system_error(critical_error))
        self.assertTrue(is_critical_error(critical_error))
        self.assertIn("0", str(user_error))


if __name__ == "__main__":
    unittest.main()
