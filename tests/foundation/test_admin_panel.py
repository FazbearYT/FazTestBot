import unittest
from unittest.mock import Mock

from core.admin_panel import (
    AdminPanelService,
    render_health,
    render_modules,
    render_overview,
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


if __name__ == "__main__":
    unittest.main()
