"""Вспомогательные утилиты SHOPCRM core (без бизнес-логики)."""
from shopcrm_core.utils.retry import (
    RetryConfig,
    TransientError,
    is_transient,
    retry_async,
)

__all__ = [
    "RetryConfig",
    "TransientError",
    "is_transient",
    "retry_async",
]
