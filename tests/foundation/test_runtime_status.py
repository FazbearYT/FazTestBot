import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from core.process_lock import ApplicationAlreadyRunningError
from core.runtime_status import RuntimeStatus, probe_liveness


class RuntimeStatusTests(unittest.TestCase):
    def test_context_publishes_atomic_ready_status_and_clears_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-status.json"
            status = RuntimeStatus(
                "5.0.1",
                6,
                path=path,
                pid=123,
                now=lambda: datetime(2026, 10, 12, 8, 30, tzinfo=timezone.utc),
            )

            with status:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    {
                        "loaded_module_count": 6,
                        "pid": 123,
                        "started_at": "2026-10-12T08:30:00Z",
                        "state": "ready",
                        "version": "5.0.1",
                    },
                    payload,
                )
                self.assertEqual([], list(path.parent.glob("*.tmp")))

            self.assertFalse(path.exists())

    def test_probe_reports_live_only_when_ready_marker_is_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-status.json"
            path.write_text(
                json.dumps(
                    {
                        "state": "ready",
                        "pid": 123,
                        "version": "5.0.1",
                        "loaded_module_count": 6,
                        "started_at": "2026-10-12T08:30:00Z",
                    }
                ),
                encoding="utf-8",
            )
            lock = Mock()
            lock.acquire.side_effect = ApplicationAlreadyRunningError("owned")

            result = probe_liveness(
                status_path=path,
                lock_path=Path(directory) / "app.lock",
                lock_factory=Mock(return_value=lock),
            )

            self.assertTrue(result.live)
            self.assertEqual(123, result.details["pid"])
            lock.release.assert_not_called()

    def test_probe_rejects_stale_marker_and_releases_probe_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-status.json"
            path.write_text(
                json.dumps(
                    {
                        "state": "ready",
                        "pid": 123,
                        "version": "5.0.1",
                        "loaded_module_count": 6,
                        "started_at": "2026-10-12T08:30:00Z",
                    }
                ),
                encoding="utf-8",
            )
            lock = Mock()

            result = probe_liveness(
                status_path=path,
                lock_path=Path(directory) / "app.lock",
                lock_factory=Mock(return_value=lock),
            )

            self.assertFalse(result.live)
            self.assertEqual("runtime status is stale", result.summary)
            lock.release.assert_called_once_with()

    def test_probe_rejects_missing_or_invalid_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-status.json"
            missing = probe_liveness(status_path=path)
            path.write_text("not-json", encoding="utf-8")
            invalid = probe_liveness(status_path=path)

            self.assertFalse(missing.live)
            self.assertEqual("runtime status is absent", missing.summary)
            self.assertFalse(invalid.live)
            self.assertEqual("runtime status is unreadable", invalid.summary)


if __name__ == "__main__":
    unittest.main()
