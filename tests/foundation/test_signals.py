import signal
import unittest
from unittest.mock import Mock, call, patch

from core.signals import ShutdownSignalHandlers


class ShutdownSignalHandlerTests(unittest.TestCase):
    def test_installs_and_restores_interrupt_and_termination_handlers(self):
        request_shutdown = Mock()
        previous = {
            signal.SIGINT: object(),
            signal.SIGTERM: object(),
        }

        with (
            patch("core.signals.signal.getsignal", side_effect=previous.__getitem__) as getsignal,
            patch("core.signals.signal.signal") as install,
        ):
            handlers = ShutdownSignalHandlers(request_shutdown)
            with handlers:
                self.assertEqual(
                    [call(signal.SIGINT), call(signal.SIGTERM)],
                    getsignal.call_args_list,
                )
                handlers._handle(signal.SIGTERM, None)

        request_shutdown.assert_called_once_with()
        self.assertEqual(signal.SIGTERM, handlers.received)
        self.assertEqual(
            [
                call(signal.SIGINT, handlers._handle),
                call(signal.SIGTERM, handlers._handle),
                call(signal.SIGINT, previous[signal.SIGINT]),
                call(signal.SIGTERM, previous[signal.SIGTERM]),
            ],
            install.call_args_list,
        )

    def test_repeated_signal_only_requests_shutdown_once(self):
        request_shutdown = Mock()
        handlers = ShutdownSignalHandlers(request_shutdown)

        handlers._handle(signal.SIGTERM, None)
        handlers._handle(signal.SIGINT, None)

        request_shutdown.assert_called_once_with()
        self.assertEqual(signal.SIGTERM, handlers.received)


if __name__ == "__main__":
    unittest.main()
