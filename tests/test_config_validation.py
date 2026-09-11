"""Тесты fail-fast валидации конфигурации core (Settings)."""
import pytest
from pydantic import ValidationError

from shopcrm_core.config import Settings, _mask_db_url


class TestMaskDbUrl:
    """Маскирование пароля в DATABASE_URL для логов."""

    def test_masks_password(self):
        url = "postgresql+asyncpg://user:secret@host:5432/db"
        assert _mask_db_url(url) == "postgresql+asyncpg://user:***@host:5432/db"

    def test_no_credentials_unchanged(self):
        url = "sqlite+aiosqlite:///:memory:"
        assert _mask_db_url(url) == url


class TestConfigValidation:
    """Валидаторы core Settings (fail-fast на старте).

    Core Settings содержит только ``DATABASE_URL``: бот-специфичные поля
    (``BOT_TOKEN``, ``ADMIN_ID``, ``FSM_STORAGE``) вынесены в конфиг
    консьюмера (``shopcrm_bot.config``).
    """

    def _make(self, **overrides):
        base = dict(
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
        )
        base.update(overrides)
        return Settings(**base)

    def test_valid_config(self):
        s = self._make()
        assert s.DATABASE_URL.startswith("sqlite+aiosqlite://")

    def test_bad_db_url_rejected(self):
        with pytest.raises(ValidationError):
            self._make(DATABASE_URL="mysql://user:pass@host/db")

    def test_valid_postgres_db_url(self):
        s = self._make(DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db")
        assert s.DATABASE_URL.startswith("postgresql+asyncpg://")
