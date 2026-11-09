# src/services/settings_service.py
"""Сервис настроек магазина (таблица ``settings``, ключ-значение).

Базовая инфраструктура для настроек, которые администратор меняет в
процессе работы (в отличие от env-конфига). Значения хранятся как текст;
интерпретация (число/флаг/строка) — за вызывающим кодом.
"""
import logging

from shopcrm_core.db.repositories.admin_repo import AdminRepository

logger = logging.getLogger(__name__)


class SettingsService:
    """Чтение/запись настроек магазина."""

    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    async def get(self, key: str) -> str | None:
        """Возвращает значение настройки (или None, если не задана)."""
        return await self.admin_repo.get_setting(key)

    async def set(self, key: str, value: str | None, updated_by: int | None = None) -> None:
        """Создаёт или обновляет настройку (upsert по ключу)."""
        await self.admin_repo.set_setting(key, value, updated_by=updated_by)

    async def get_int(self, key: str, default: int | None = None) -> int | None:
        """Возвращает настройку как int (или ``default``, если не задана/не число)."""
        raw = await self.admin_repo.get_setting(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            logger.warning(f"Setting '{key}' is not a valid int: {raw!r}")
            return default
