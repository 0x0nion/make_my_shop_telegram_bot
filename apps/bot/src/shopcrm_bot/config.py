"""Конфигурация self-hosted бота SHOPCRM.

Наследует базовый конфиг core (``DATABASE_URL``, ``LOG_LEVEL``, ``DEBUG``,
``LOGS_DIR``) и добавляет бот-специфичные настройки (``BOT_TOKEN``,
``ADMIN_ID``, ``FSM_STORAGE``, ``REDIS_URL``). Core остаётся чистой
библиотекой без зависимостей от Telegram.
"""
from typing import List

from pydantic import SecretStr, field_validator

from shopcrm_core.config import Settings as CoreSettings

# Разрешённые бэкенды хранения FSM.
_ALLOWED_FSM_STORAGE = ("memory", "redis")


class Settings(CoreSettings):
    """Конфиг бота: core-настройки + Telegram/FSM."""

    BOT_TOKEN: SecretStr
    ADMIN_ID: List[int]

    # FSM storage backend: "memory" (default, single process) or "redis" (shared/persistent).
    FSM_STORAGE: str = "memory"
    # Redis connection URL, used only when FSM_STORAGE == "redis".
    REDIS_URL: str = "redis://localhost:6379/0"
    # Language for admin notifications (order cards, payment alerts): ru/en/es.
    NOTIFICATIONS_LANG: str = "ru"

    @field_validator("ADMIN_ID")
    @classmethod
    def _validate_admin_id(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("ADMIN_ID must not be empty")
        if any(x <= 0 for x in v):
            raise ValueError("ADMIN_ID values must be positive integers")
        return v

    @field_validator("FSM_STORAGE")
    @classmethod
    def _validate_fsm_storage(cls, v: str) -> str:
        normalized = v.lower()
        if normalized not in _ALLOWED_FSM_STORAGE:
            raise ValueError(f"FSM_STORAGE must be one of {list(_ALLOWED_FSM_STORAGE)}")
        return normalized


config = Settings()
