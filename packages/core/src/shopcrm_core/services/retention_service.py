# src/services/retention_service.py
"""Политика хранения (retention) журналов аудита.

Core предоставляет только метод очистки; запуск периодической очистки
(фоновая задача) — за консьюмером (ботом). Сервис stateless: сессия
инжектируется извне.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shopcrm_core.db.models.order import OrderStatusHistory

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    """Текущее время UTC без timezone.

    ``created_at`` хранится как naive (``server_default=func.now()``),
    поэтому cutoff считаем в том же формате, чтобы сравнение в БД
    было корректным (SQLite и PostgreSQL).
    """
    return datetime.now(UTC).replace(tzinfo=None)


class RetentionService:
    """Очистка старых записей журналов аудита по политике хранения."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def cleanup_order_status_history(self, retention_days: int) -> int:
        """Удаляет записи ``order_status_history`` старше ``retention_days``.

        :param retention_days: сколько дней хранить; ``<= 0`` — очистка отключена.
        :return: количество удалённых записей (0, если очистка отключена).
        """
        if retention_days is None or retention_days <= 0:
            return 0

        cutoff = _utcnow_naive() - timedelta(days=retention_days)
        result = await self.session.execute(
            delete(OrderStatusHistory).where(OrderStatusHistory.created_at < cutoff)
        )
        await self.session.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info(
                f"Retention: deleted {deleted} order_status_history rows "
                f"older than {retention_days} days"
            )
        return deleted
