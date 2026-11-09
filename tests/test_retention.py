"""Тесты политики хранения (retention) журналов аудита (order_status_history).

Проверяют:
  - отключённая очистка (retention_days <= 0) ничего не удаляет;
  - удаляются только записи старше retention_days;
  - свежие записи сохраняются;
  - ошибка БД пробрасывается наружу (цикл бота её ловит).
"""
from datetime import UTC, datetime, timedelta

import pytest
from shopcrm_core.db.models.order import Order, OrderStatusHistory
from shopcrm_core.services.retention_service import RetentionService
from sqlalchemy import func, select


def _naive(dt: datetime) -> datetime:
    """Обрезает timezone (created_at хранится как naive)."""
    return dt.replace(tzinfo=None)


async def _count_history(session) -> int:
    return (await session.execute(select(func.count()).select_from(OrderStatusHistory))).scalar() or 0


async def _seed_history(session, user_id: int, ages_days: list[int]) -> Order:
    """Создаёт заказ и записи журнала с заданным возрастом (в днях)."""
    order = Order(user_id=user_id, total_price=10.0, status="pending")
    session.add(order)
    await session.commit()
    await session.refresh(order)

    now = datetime.now(UTC)
    rows = [
        OrderStatusHistory(
            order_id=order.id,
            old_status="pending",
            new_status="processing",
            changed_by=user_id,
            created_at=_naive(now - timedelta(days=age)),
        )
        for age in ages_days
    ]
    session.add_all(rows)
    await session.commit()
    return order


class TestRetentionDisabled:
    async def test_zero_days_returns_zero(self, session, user_a):
        """retention_days=0 — очистка отключена, ничего не удаляется."""
        await _seed_history(session, user_a.id, [300, 100, 1])
        deleted = await RetentionService(session).cleanup_order_status_history(0)
        assert deleted == 0
        assert await _count_history(session) == 3

    async def test_negative_days_returns_zero(self, session, user_a):
        """Отрицательное значение — очистка отключена."""
        await _seed_history(session, user_a.id, [300, 100, 1])
        deleted = await RetentionService(session).cleanup_order_status_history(-5)
        assert deleted == 0
        assert await _count_history(session) == 3


class TestRetentionCleanup:
    async def test_deletes_only_old_rows(self, session, user_a):
        """retention=180: удаляется только запись 300-дневной давности."""
        await _seed_history(session, user_a.id, [300, 100, 1])
        deleted = await RetentionService(session).cleanup_order_status_history(180)
        assert deleted == 1
        assert await _count_history(session) == 2

    async def test_recent_rows_preserved(self, session, user_a):
        """retention=50: свежие записи (100 и 1 день) — удаляются, 1 день сохраняется."""
        await _seed_history(session, user_a.id, [300, 100, 1])
        deleted = await RetentionService(session).cleanup_order_status_history(50)
        assert deleted == 2  # 300 и 100 дней
        assert await _count_history(session) == 1

    async def test_empty_table_returns_zero(self, session, user_a):
        """Пустая таблица: 0 удалено, без ошибок."""
        deleted = await RetentionService(session).cleanup_order_status_history(180)
        assert deleted == 0

    async def test_error_propagates(self, user_a):
        """Ошибка БД пробрасывается наружу (цикл бота её ловит и не роняет бота)."""

        class _FailingSession:
            async def execute(self, *args, **kwargs):
                raise RuntimeError("DB error")

            async def commit(self):
                pass

        service = RetentionService(_FailingSession())
        with pytest.raises(RuntimeError):
            await service.cleanup_order_status_history(180)
