import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from modules.media_downloader.handlers import DISABLED_MESSAGE, MediaDownloaderModule


def make_call(*, data: str = "module_media_downloader", actor_id: int = 7, chat_id: int = 11):
    return SimpleNamespace(
        id="callback-id",
        data=data,
        from_user=SimpleNamespace(id=actor_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=13),
    )


class DisabledMediaDownloaderTests(unittest.TestCase):
    def setUp(self):
        self.module = MediaDownloaderModule(
            module_id="media_downloader",
            name="Media Downloader",
            description="disabled",
            icon="📥",
            version="1.3.1",
            callback_prefix="media_",
        )

    def test_entry_only_exposes_navigation_and_records_scoped_message(self):
        bot = Mock()
        call = make_call()

        self.module.handle_entry(bot, call)

        bot.edit_message_text.assert_called_once()
        sent = bot.edit_message_text.call_args.kwargs
        self.assertEqual(sent["text"], DISABLED_MESSAGE)
        buttons = [button for row in sent["reply_markup"].keyboard for button in row]
        self.assertEqual([button.callback_data for button in buttons], ["media_back_to_modules"])
        self.assertEqual(self.module.get_interaction_state(7, 11, "message_id"), 13)
        self.assertIsNone(self.module.get_interaction_state(8, 11, "message_id"))

    def test_disabled_action_is_answered_once_without_work(self):
        bot = Mock()
        call = make_call(data="media_video")

        self.module.handle_callback(bot, call)

        bot.answer_callback_query.assert_called_once_with(
            "callback-id", "⚠️ Модуль временно отключён", show_alert=True
        )
        bot.edit_message_text.assert_not_called()

    def test_admin_snapshot_reports_disabled_state(self):
        snapshot = self.module.get_admin_snapshot()

        self.assertEqual(snapshot.status, "disabled")
        self.assertEqual(snapshot.active_state_count, 0)
        self.assertEqual(snapshot.summary, "media download backend is not enabled")


if __name__ == "__main__":
    unittest.main()
