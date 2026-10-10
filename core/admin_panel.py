"""Typed application service and HTML rendering for the admin dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

from core.health import HealthReport, build_health_report
from core.module_base import ModuleAdminSnapshot
from core.settings import Settings


@dataclass(frozen=True, slots=True)
class AdminDashboard:
    total_users: int
    active_users: int
    total_operations: int
    today_operations: int
    cipher_distribution: dict[str, int]
    modules: tuple[ModuleAdminSnapshot, ...]
    health: HealthReport


class AdminPanelService:
    """Compose admin data without coupling Telegram handlers to storage details."""

    def __init__(
        self,
        admin_manager: Any,
        module_manager: Any,
        settings: Settings,
        *,
        health_provider: Any = build_health_report,
    ):
        self.admin_manager = admin_manager
        self.module_manager = module_manager
        self.settings = settings
        self.health_provider = health_provider

    def get_dashboard(self) -> AdminDashboard:
        stats = self.admin_manager.get_global_stats()
        modules = tuple(self.module_manager.get_admin_snapshots())
        health = self.health_provider(self.settings)
        return AdminDashboard(
            total_users=stats["total_users"],
            active_users=stats["active_users"],
            total_operations=stats["total_operations"],
            today_operations=stats["today_operations"],
            cipher_distribution=dict(stats["cipher_distribution"]),
            modules=modules,
            health=health,
        )


def render_overview(dashboard: AdminDashboard) -> str:
    health_icon = "✅" if dashboard.health.ready else "❌"
    return (
        "👑 <b>Админ-панель — Обзор</b>\n\n"
        f"👥 Пользователей: <b>{dashboard.total_users}</b>\n"
        f"✅ Активно за неделю: <b>{dashboard.active_users}</b>\n"
        f"⚙️ Операций: <b>{dashboard.total_operations}</b>\n"
        f"📅 Сегодня: <b>{dashboard.today_operations}</b>\n"
        f"🧩 Загружено модулей: <b>{len(dashboard.modules)}</b>\n"
        f"{health_icon} Готовность: <b>{'готов' if dashboard.health.ready else 'не готов'}</b>"
    )


def render_modules(dashboard: AdminDashboard) -> str:
    lines = ["🧩 <b>Админ-панель — Модули</b>", ""]
    if not dashboard.modules:
        lines.append("Загруженные модули отсутствуют.")
    for module in dashboard.modules:
        lines.extend(
            [
                f"{escape(module.icon)} <b>{escape(module.name)}</b> v{escape(module.version)}",
                f"Статус: {escape(module.status)} · {escape(module.summary)}",
                f"Активных состояний: {module.active_state_count}",
                f"ID: <code>{escape(module.module_id)}</code>",
            ]
        )
        for metric in module.metrics:
            lines.append(f"• {escape(metric.label)}: {escape(str(metric.value))}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_health(dashboard: AdminDashboard) -> str:
    lines = ["🩺 <b>Админ-панель — Готовность</b>", ""]
    icons = {"ok": "✅", "warning": "⚠️", "error": "❌"}
    for check in dashboard.health.checks:
        lines.append(
            f"{icons.get(check.status, '•')} <b>{escape(check.name)}</b>: {escape(check.summary)}"
        )
    return "\n".join(lines)


__all__ = [
    "AdminDashboard",
    "AdminPanelService",
    "render_health",
    "render_modules",
    "render_overview",
]
