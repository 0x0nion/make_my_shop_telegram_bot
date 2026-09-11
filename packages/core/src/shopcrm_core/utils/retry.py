"""Повторные попытки (retry) с экспоненциальным backoff для временных ошибок.

Используется для обёртки операций, которые могут упасть из-за временных
сбоев (соединение БД, лимиты Telegram API и т.п.).
"""
import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Tuple, Type, TypeVar

from shopcrm_core.logging import logger

T = TypeVar("T")


class TransientError(Exception):
    """Явная пометка: ошибка временная, повтор имеет смысл."""


@dataclass(frozen=True)
class RetryConfig:
    """Параметры повторных попыток.

    :param max_attempts: максимальное число попыток (включая первую).
    :param base_delay: базовая задержка в секундах.
    :param max_delay: потолок задержки в секундах.
    :param multiplier: множитель экспоненциального backoff.
    :param jitter: добавляемая случайная задержка (0..jitter) в секундах.
    """

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    multiplier: float = 2.0
    jitter: float = 0.25


def is_transient(
    exc: BaseException,
    extra: Tuple[Type[BaseException], ...] = (),
) -> bool:
    """Определяет, является ли исключение временным (повтор имеет смысл).

    Временными считаются:
    - `TransientError` (явная пометка);
    - ошибки сети/таймаутов (`ConnectionError`, `TimeoutError`);
    - типы, переданные в `extra` (например, конкретные ошибки aiogram/SQLAlchemy).
    """
    if isinstance(exc, TransientError):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if extra and isinstance(exc, extra):
        return True
    return False


def _compute_delay(attempt: int, cfg: RetryConfig) -> float:
    """Задержка перед попыткой `attempt` (1-based) с экспоненциальным backoff и jitter."""
    delay = cfg.base_delay * (cfg.multiplier ** (attempt - 1))
    delay = min(delay, cfg.max_delay)
    if cfg.jitter > 0:
        delay += random.uniform(0, cfg.jitter)
    return delay


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    config: RetryConfig | None = None,
    retry_on: Tuple[Type[BaseException], ...] = (),
    name: str = "operation",
) -> T:
    """Выполняет асинхронный `func` с повторами при временных ошибках.

    :param func: нулевой аргументный корутинный вызов (например, лямбда).
    :param config: параметры повторов (по умолчанию `RetryConfig()`).
    :param retry_on: дополнительные типы исключений, считающиеся временными.
    :param name: человекочитаемое имя операции для логов.
    :return: результат `func`.
    :raises: последнее исключение, если все попытки исчерпаны.
    """
    cfg = config or RetryConfig()
    max_attempts = max(1, cfg.max_attempts)
    last_exc: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001 — намеренно широкий перехват
            if not is_transient(exc, extra=retry_on):
                raise
            last_exc = exc
            if attempt >= max_attempts:
                logger.error(
                    f"Retry: '{name}' failed after {attempt} attempts: {exc!r}"
                )
                break
            delay = _compute_delay(attempt, cfg)
            logger.warning(
                f"Retry: '{name}' attempt {attempt}/{max_attempts} failed "
                f"({exc!r}); retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)

    # Все попытки исчерпаны — пробрасываем последнее исключение.
    assert last_exc is not None
    raise last_exc
