"""Конфигурация self-hosted бота SHOPCRM.

Наследует базовый конфиг core (``DATABASE_URL``, ``LOG_LEVEL``, ``DEBUG``,
``LOGS_DIR``) и добавляет бот-специфичные настройки (``BOT_TOKEN``,
``ADMIN_ID``, ``FSM_STORAGE``, ``REDIS_URL``). Core остаётся
самодостаточным, без зависимостей от Telegram.
"""

from pydantic import SecretStr, field_validator
from shopcrm_core.config import Settings as CoreSettings

# Разрешённые бэкенды хранения FSM.
_ALLOWED_FSM_STORAGE = ("memory", "redis")


class Settings(CoreSettings):
    """Конфиг бота: core-настройки + Telegram/FSM."""

    BOT_TOKEN: SecretStr
    ADMIN_ID: list[int]

    # FSM storage backend: "memory" (default, single process) or "redis" (shared/persistent).
    FSM_STORAGE: str = "memory"
    # Redis connection URL, used only when FSM_STORAGE == "redis".
    REDIS_URL: str = "redis://localhost:6379/0"

    # URL of the shop manager (Telegram profile) for the "Manager" button
    # on the product card. If empty, the button is hidden.
    MANAGER_URL: str = ""

    # ==================== РАССЫЛКА (BROADCAST) ====================
    # Сколько часов «охлаждения» после отправки: пользователям, которым уже
    # присылали в этом окне, повторная рассылка не отправляется (анти-спам).
    # По умолчанию отключён (0): защита от параллельных рассылок уже есть —
    # новую рассылку нельзя запустить, пока не завершилась предыдущая.
    # > 0 включает окно cooldown.
    BROADCAST_COOLDOWN_HOURS: float = 0.0
    # Лимит отправки сообщений (сообщений в секунду на магазин).
    BROADCAST_MAX_RPS: float = 10.0
    # Сколько сообщений отправляется параллельно (семафор).
    BROADCAST_CONCURRENCY: int = 10
    # Размер чанка: получателей за один проход + коммит отметок.
    BROADCAST_CHUNK_SIZE: int = 50
    # Сколько раз повторять отправку при временных сбоях (сеть/429).
    BROADCAST_RETRY_ATTEMPTS: int = 3
    # Базовая задержка между повторами при сетевых сбоях (сек, растёт линейно).
    BROADCAST_RETRY_DELAY: float = 5.0
    # Прерванные рассылки старше этого возраста (часов) не возобновляются
    # автоматически после рестарта бота. <= 0 отключает авто-возобновление.
    BROADCAST_RESUME_MAX_AGE_HOURS: float = 24.0

    @field_validator("ADMIN_ID")
    @classmethod
    def _validate_admin_id(cls, v: list[int]) -> list[int]:
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
