"""Регрессионные тесты IsAdminFilter.

Проверяют, что сигнатура фильтра совместима с тем, как aiogram 3 передаёт
workflow data (поимённо через kwargs), и что логика контроля доступа
работает корректно.

Регрессия: ранее фильтр принимал ``data: Dict[str, Any]``, которого aiogram
никогда не передаёт → ``TypeError`` на любом сообщении (даже клиентском),
потому что root-фильтр админ-роутера проверяется для всех событий.
"""
from types import SimpleNamespace

from shopcrm_bot.config import config
from shopcrm_bot.filters.admin import IsAdminFilter


def _event(user_id: int | None) -> SimpleNamespace:
    """Минимальное событие: фильтр читает только ``event.from_user.id``."""
    from_user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(from_user=from_user)


class TestIsAdminFilter:
    async def test_admin_allowed(self):
        """Пользователь из admin_ids пропущен."""
        assert await IsAdminFilter()(_event(1), admin_ids=[1]) is True

    async def test_non_admin_denied(self):
        """Пользователь не из admin_ids заблокирован."""
        assert await IsAdminFilter()(_event(2), admin_ids=[1]) is False

    async def test_fallback_to_config_when_admin_ids_missing(self):
        """Без admin_ids — фолбэк на config.ADMIN_ID."""
        admin_id = config.ADMIN_ID[0]
        non_admin_id = max(config.ADMIN_ID) + 1
        assert await IsAdminFilter()(_event(admin_id)) is True
        assert await IsAdminFilter()(_event(non_admin_id)) is False

    async def test_fallback_to_config_when_admin_ids_none(self):
        """Явный None — фолбэк на config.ADMIN_ID."""
        admin_id = config.ADMIN_ID[0]
        assert await IsAdminFilter()(_event(admin_id), admin_ids=None) is True

    async def test_no_from_user_denied(self):
        """Событие без from_user — доступ запрещён."""
        assert await IsAdminFilter()(_event(None), admin_ids=[1]) is False
