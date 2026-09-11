"""Тесты парсинга конфигурации из environment variables."""
import os
import pytest
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class _TestSettings(BaseSettings):
    """Копия Settings для изолированного тестирования (без импорта config)."""
    BOT_TOKEN: SecretStr
    DATABASE_URL: str
    ADMIN_ID: list[int]
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    FSM_STORAGE: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"
    LOGS_DIR: str = "logs"

    model_config = SettingsConfigDict(env_file=None)  # не читаем .env


class TestConfigDefaults:
    """Значения по умолчанию."""

    def test_log_level_default(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert s.LOG_LEVEL == "INFO"

    def test_debug_default(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert s.DEBUG is False

    def test_fsm_storage_default(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert s.FSM_STORAGE == "memory"

    def test_redis_url_default(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert s.REDIS_URL == "redis://localhost:6379/0"

    def test_logs_dir_default(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert s.LOGS_DIR == "logs"


class TestConfigEnvParsing:
    """Переопределение через env vars."""

    def test_bot_token_is_secret(self):
        s = _TestSettings(BOT_TOKEN="123:ABC", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert isinstance(s.BOT_TOKEN, SecretStr)
        assert s.BOT_TOKEN.get_secret_value() == "123:ABC"

    def test_admin_id_list(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1, 2, 3])
        assert s.ADMIN_ID == [1, 2, 3]

    def test_debug_true(self):
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1], DEBUG=True)
        assert s.DEBUG is True

    def test_fsm_storage_redis(self):
        s = _TestSettings(
            BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1],
            FSM_STORAGE="redis", REDIS_URL="redis://myhost:6380/1",
        )
        assert s.FSM_STORAGE == "redis"
        assert s.REDIS_URL == "redis://myhost:6380/1"

    def test_env_var_override(self, monkeypatch):
        """Env var переопределяет дефолт."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = _TestSettings(BOT_TOKEN="x", DATABASE_URL="sqlite://", ADMIN_ID=[1])
        assert s.LOG_LEVEL == "DEBUG"


class TestRealConfig:
    """Проверка, что реальный config (с .env) импортируется корректно."""

    def test_config_importable(self):
        from shopcrm_core.config import get_config
        cfg = get_config()
        assert cfg.DATABASE_URL == "sqlite+aiosqlite:///:memory:"
