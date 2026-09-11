from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shopcrm_core.logging import logger

# Разрешённые асинхронные драйверы БД (fail-fast на старте).
_ALLOWED_DB_DRIVERS = ("postgresql+asyncpg://", "sqlite+aiosqlite://")


def _mask_db_url(url: str) -> str:
    """Маскирует пароль в DATABASE_URL для безопасного логирования."""
    if "@" not in url:
        return url
    credentials, host_part = url.rsplit("@", 1)
    if ":" in credentials:
        user, _ = credentials.rsplit(":", 1)
        return f"{user}:***@{host_part}"
    return f"{credentials}@{host_part}"


class Settings(BaseSettings):
    """Конфигурация core: только данные (БД) и логирование.

    Core — библиотека, поэтому здесь нет бот-специфичных полей
    (BOT_TOKEN, ADMIN_ID, FSM_STORAGE, REDIS_URL) — они живут в конфиге
    консьюмера (например, ``shopcrm_bot.config``).
    """

    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    # Directory for rotating log files (relative to the working directory).
    LOGS_DIR: str = "logs"

    # ``extra="ignore"``: core — библиотека, поэтому неизвестные env-переменные
    # (BOT_TOKEN, ADMIN_ID и т.д. — поля консьюмера) игнорируются, а не
    # вызывают ошибку валидации.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        if not v.startswith(_ALLOWED_DB_DRIVERS):
            raise ValueError(
                f"DATABASE_URL must start with one of {_ALLOWED_DB_DRIVERS}"
            )
        return v

    @model_validator(mode="after")
    def _log_summary(self) -> "Settings":
        logger.info(
            "Config loaded: DEBUG={} LOG_LEVEL={} DB={}",
            self.DEBUG,
            self.LOG_LEVEL,
            _mask_db_url(self.DATABASE_URL),
        )
        return self


@lru_cache(maxsize=1)
def get_config() -> Settings:
    """Ленивое создание конфига core.

    Импорт модуля без env-переменных безопасен: ``Settings()`` создаётся
    только при первом вызове ``get_config()``.
    """
    return Settings()

