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
    return _bounded("\n".join(lines).rstrip())


def render_health(dashboard: AdminDashboard) -> str:
    lines = ["🩺 <b>Админ-панель — Готовность</b>", ""]
    icons = {"ok": "✅", "warning": "⚠️", "error": "❌"}
    for check in dashboard.health.checks:
        lines.append(
            f"{icons.get(check.status, '•')} <b>{escape(check.name)}</b>: {escape(check.summary)}"
        )
    return _bounded("\n".join(lines))


def _bounded(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    cutoff = text.rfind("\n", 0, limit - 20)
    if cutoff <= 0:
        cutoff = limit - 20
    return text[:cutoff].rstrip() + "\n\n<i>… сокращено</i>"


def _safe(value: Any, limit: int = 500) -> str:
    text = str(value)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return escape(text)


def render_user_profile(user_id: int, profile: dict[str, Any]) -> str:
    lines = [
        f"👤 <b>Профиль пользователя</b> (ID: {user_id})",
        "",
        f"Имя: {_safe(profile['full_name'])}",
        f"Юзернейм: @{_safe(profile['username'])}",
        f"Первое взаимодействие: {_safe(profile['created_at'])}",
        f"Последняя активность: {_safe(profile['last_active'])}",
        "",
        "<b>Статистика модулей:</b>",
    ]
    for module, count in profile["module_stats"].items():
        lines.append(f"• {_safe(module)}: {count} операций")
    lines.extend(["", "<b>Последние операции:</b>"])
    names = {"morze": "Морзе", "numbers": "Числа", "caesar": "Цезарь", "qr": "QR"}
    for index, operation in enumerate(profile["last_operations"], 1):
        timestamp = str(operation["timestamp"])
        parts = timestamp.split()
        time_text = parts[1][:5] if len(parts) > 1 else timestamp
        cipher = names.get(operation["cipher_type"], str(operation["cipher_type"]))
        lines.append(f"{index}. [{escape(time_text)}] {escape(cipher)}:")
        lines.append(
            f"   «{_safe(operation['original_text'])}» → «{_safe(operation['encrypted_text'])}»"
        )
    return _bounded("\n".join(lines))


def render_search_results(query: str, results: list[dict[str, Any]]) -> str:
    safe_query = _safe(query)
    if not results:
        return f"⚠️ По запросу «{safe_query}» ничего не найдено."
    lines = [
        f"🔍 <b>Результаты поиска</b> по «{safe_query}»",
        "",
        f"Найдено операций: {len(results)}",
        "",
    ]
    names = {"morze": "Морзе", "numbers": "Числа", "caesar": "Цезарь", "qr": "QR"}
    for index, operation in enumerate(results[:10], 1):
        timestamp = str(operation["timestamp"])
        parts = timestamp.split()
        stamp = " ".join(parts[:2]) if len(parts) > 1 else timestamp
        cipher = names.get(operation["cipher_type"], str(operation["cipher_type"]))
        lines.extend(
            [
                f"{index}. [{escape(stamp)}] ID {operation['user_id']} | {escape(cipher)}",
                f"   Исходный: «{_safe(operation['original_text'])}»",
                f"   Результат: «{_safe(operation['encrypted_text'])}»",
                "",
            ]
        )
    if len(results) > 10:
        lines.append(f"<i>… и ещё {len(results) - 10} операций</i>")
    return _bounded("\n".join(lines))


def render_backup_overview(settings: Settings) -> str:
    enabled = "включены" if settings.backup_enabled else "отключены"
    return (
        "🗄️ <b>Админ-панель — Бэкапы</b>\n\n"
        "Управление резервными копиями базы данных:\n"
        f"• Автоматические бэкапы: {enabled}\n"
        f"• Время запуска: {_safe(settings.backup_time)}\n"
        f"• Хранение: до {settings.backup_retention_count} копий / "
        f"{settings.backup_retention_days} дней\n"
        "• Ручное создание по необходимости\n\n"
        "Выберите действие:"
    )


def render_restore_instructions(filename: str) -> str:
    return (
        "🗄️ <b>Восстановление базы данных</b>\n\n"
        "Онлайн-восстановление отключено: замена рабочей БД во время работы бота "
        "может привести к несогласованному состоянию.\n\n"
        "Остановите бот и выполните восстановление операторским CLI для файла:\n"
        f"<code>{_safe(filename)}</code>\n\n"
        "Команда: <code>python -m scripts.database restore --backup-file "
        f"{_safe(filename)}</code>\n\n"
        "После восстановления выполните проверку БД и только затем запустите бот."
    )


__all__ = [
    "AdminDashboard",
    "AdminPanelService",
    "render_health",
    "render_backup_overview",
    "render_modules",
    "render_overview",
    "render_restore_instructions",
    "render_search_results",
    "render_user_profile",
]
