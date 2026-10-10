import tempfile
import unittest
from pathlib import Path

from core.process_lock import ApplicationAlreadyRunningError, ApplicationLock


class ApplicationLockTests(unittest.TestCase):
    def test_second_owner_is_rejected_until_first_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "application.lock"
            first = ApplicationLock(path)
            second = ApplicationLock(path)
            first.acquire()

            with self.assertRaises(ApplicationAlreadyRunningError):
                second.acquire()

            first.release()
            second.acquire()
            second.release()

    def test_release_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = ApplicationLock(Path(directory) / "application.lock")
            lock.acquire()
            lock.release()
            lock.release()


if __name__ == "__main__":
    unittest.main()
