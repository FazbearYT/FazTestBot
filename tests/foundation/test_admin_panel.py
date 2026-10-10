import unittest
from datetime import datetime
from unittest.mock import Mock

from core.admin_panel import (
    AdminPanelService,
    render_backup_info,
    render_backup_overview,
    render_backup_result,
    render_backup_stats,
    render_health,
    render_modules,
    render_overview,
    render_restore_instructions,
    render_search_results,
    render_user_profile,
)
from core.health import HealthCheck, HealthReport
from core.module_base import BaseModule, ModuleAdminSnapshot
from core.settings import Settings


class SampleModule(BaseModule):
    def __init__(self):
        super().__init__("sample", "Sample", "Description", "🧪", "1.2.3")

    def handle_entry(self, bot, call):
        pass

    def handle_callback(self, bot, call):
        pass

    def get_menu_keyboard(self):
        return None


class AdminPanelTests(unittest.TestCase):
    def setUp(self):
        self.module = ModuleAdminSnapshot(
            module_id="sample",
            name="Sample <Module>",
            icon="🧪",
            version="1.2.3",
            callback_prefix="sample_",
            status="ok",
            summary="module loaded",
            active_state_count=2,
        )
        self.health = HealthReport(
            ready=True,
            checks=(HealthCheck("database", "ok", "database is current", {}),),
        )
        self.admin_manager = Mock()
        self.admin_manager.get_global_stats.return_value = {
            "total_users": 10,
            "active_users": 4,
            "total_operations": 25,
            "today_operations": 3,
            "cipher_distribution": {"morze": 25},
        }
        self.module_manager = Mock()
        self.module_manager.get_admin_snapshots.return_value = [self.module]

    def dashboard(self):
        service = AdminPanelService(
            self.admin_manager,
            self.module_manager,
            Settings(bot_token="configured"),
            health_provider=Mock(return_value=self.health),
        )
        return service.get_dashboard()

    def test_service_composes_storage_modules_and_health(self):
        dashboard = self.dashboard()

        self.assertEqual(10, dashboard.total_users)
        self.assertEqual((self.module,), dashboard.modules)
        self.assertTrue(dashboard.health.ready)
        self.admin_manager.get_global_stats.assert_called_once_with()
        self.module_manager.get_admin_snapshots.assert_called_once_with()

    def test_renderers_escape_module_control_text(self):
        dashboard = self.dashboard()

        overview = render_overview(dashboard)
        modules = render_modules(dashboard)
        health = render_health(dashboard)

        self.assertIn("Загружено модулей: <b>1</b>", overview)
        self.assertIn("Sample &lt;Module&gt;", modules)
        self.assertNotIn("Sample <Module>", modules)
        self.assertIn("database is current", health)

    def test_base_module_snapshot_contract_is_safe_and_count_only(self):
        module = SampleModule()
        module.set_user_state(101, "mode", "waiting")
        snapshot = module.get_admin_snapshot()

        self.assertFalse(hasattr(snapshot, "user_ids"))
        self.assertFalse(hasattr(snapshot, "state"))
        self.assertEqual(1, snapshot.active_state_count)
        self.assertEqual("sample", snapshot.module_id)

    def test_profile_and_search_renderers_escape_dynamic_html(self):
        profile = {
            "full_name": "<b>owner</b>",
            "username": "name&more",
            "created_at": "2026-01-01 10:00:00",
            "last_active": "2026-01-02 10:00:00",
            "module_stats": {"<module>": "<count>"},
            "last_operations": [
                {
                    "cipher_type": "<cipher>",
                    "original_text": "<secret>",
                    "encrypted_text": "a&b",
                    "timestamp": "2026-01-02 10:00:00",
                }
            ],
        }
        results = [
            {
                "user_id": "<id>",
                "cipher_type": "<cipher>",
                "original_text": "<original>",
                "encrypted_text": "a&b",
                "timestamp": "2026-01-02 10:00:00",
            }
        ]

        profile_text = render_user_profile(5, profile)
        search_text = render_search_results("<query>", results)

        self.assertNotIn("<secret>", profile_text)
        self.assertIn("&lt;secret&gt;", profile_text)
        self.assertIn("&lt;query&gt;", search_text)
        self.assertIn("a&amp;b", search_text)
        self.assertIn("&lt;count&gt;", profile_text)
        self.assertIn("&lt;id&gt;", search_text)

    def test_rendered_search_is_bounded_for_telegram(self):
        results = [
            {
                "user_id": index,
                "cipher_type": "cipher",
                "original_text": "x" * 1000,
                "encrypted_text": "y" * 1000,
                "timestamp": "2026-01-02 10:00:00",
            }
            for index in range(20)
        ]

        self.assertLessEqual(len(render_search_results("query", results)), 3900)

    def test_backup_views_use_settings_and_disable_online_restore(self):
        settings = Settings(
            backup_enabled=False,
            backup_time="04:30",
            backup_retention_count=9,
            backup_retention_days=45,
        )

        overview = render_backup_overview(settings)
        restore = render_restore_instructions("users_manual_<unsafe>.db")

        self.assertIn("04:30", overview)
        self.assertIn("до 9 копий / 45 дней", overview)
        self.assertIn("Онлайн-восстановление отключено", restore)
        self.assertIn("users_manual_&lt;unsafe&gt;.db", restore)

        result = render_backup_result("failed: <filesystem>", 1)
        stats = render_backup_stats(
            {
                "total_count": 1,
                "auto_count": 0,
                "manual_count": 1,
                "total_size_formatted": "<1 KB>",
                "newest": "<now>",
                "oldest": "<then>",
            }
        )
        info = render_backup_info(
            {
                "filename": "<backup>.db",
                "size_formatted": "<1 KB>",
                "created": datetime(2026, 1, 1),
                "type": "<manual>",
            }
        )
        self.assertIn("&lt;filesystem&gt;", result)
        self.assertIn("&lt;1 KB&gt;", stats)
        self.assertIn("&lt;backup&gt;.db", info)


if __name__ == "__main__":
    unittest.main()
