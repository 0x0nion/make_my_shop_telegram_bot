# database/repositories/order_audit.py
"""Общая логика смены статуса заказа с записью в журнал аудита.

Используется и админским, и клиентским репозиториями: любая смена статуса
заказа фиксируется в ``order_status_history`` (кто, когда, из чего в что),
а на самом заказе выставляются поля аудита (``paid_at``/``paid_by``,
``completed_at``, ``cancelled_at``).
"""
from datetime import UTC, datetime

from sqlalchemy.orm import joinedload, selectinload

from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.order import Order, OrderStatusHistory
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger

# Статусы, при достижении которых заказ считается оплаченным
# (админ подтвердил оплату / заказ в процессе исполнения).
PAID_STATUSES = frozenset({
    OrderStatus.PROCESSING.value,
    OrderStatus.READY_FOR_PICKUP.value,
    OrderStatus.DELIVERING.value,
    OrderStatus.COMPLETED.value,
})


class OrderAuditMixin:
    """Смена статуса заказа + запись в журнал аудита (общая для admin/user)."""

    @property
    def _order_audit_repo(self) -> BaseRepository[Order]:
        return BaseRepository(Order, self.session)

    def _apply_status_change(
        self,
        order: Order,
        new_status: str,
        changed_by: int | None = None,
        reason: str | None = None,
    ) -> Order:
        """Применяет смену статуса к уже загруженному заказу (без commit).

        Выставляет поля аудита (``paid_at``/``paid_by``, ``completed_at``,
        ``cancelled_at``) и добавляет строку в журнал ``order_status_history``.
        Коммит выполняет вызывающий код.
        """
        old_status = order.status
        if old_status == new_status:
            return order

        now = datetime.now(UTC)
        order.status = new_status

        if new_status in PAID_STATUSES and not order.paid_at:
            order.paid_at = now
            if order.paid_by is None:
                order.paid_by = changed_by
        if new_status == OrderStatus.COMPLETED.value:
            order.completed_at = now
        elif new_status == OrderStatus.CANCELLED.value:
            order.cancelled_at = now

        self.session.add(OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        ))
        return order

    async def change_order_status(
        self,
        order_id: int,
        new_status: str,
        changed_by: int | None = None,
        reason: str | None = None,
    ) -> Order | None:
        """Меняет статус заказа и фиксирует смену в журнале аудита.

        Автоматически выставляет ``paid_at``/``paid_by`` при переходе в
        оплаченный статус, ``completed_at`` при ``completed``,
        ``cancelled_at`` при ``cancelled``.
        """
        options = [joinedload(Order.user), selectinload(Order.items)]
        order = await self._order_audit_repo.get_by_id(order_id, options=options)
        if not order:
            return None

        self._apply_status_change(order, new_status, changed_by, reason)
        logger.info(f"Order {order_id}: status -> {new_status} (by {changed_by})")
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def mark_order_paid(
        self,
        order_id: int,
        changed_by: int | None = None,
    ) -> Order | None:
        """Отмечает заказ как оплаченный (``is_paid`` + ``paid_at``/``paid_by``)."""
        options = [joinedload(Order.user), selectinload(Order.items)]
        order = await self._order_audit_repo.get_by_id(order_id, options=options)
        if not order:
            return None

        now = datetime.now(UTC)
        order.is_paid = True
        if not order.paid_at:
            order.paid_at = now
        if order.paid_by is None:
            order.paid_by = changed_by

        logger.info(f"Order {order_id} marked as paid (by {changed_by})")
        await self.session.commit()
        await self.session.refresh(order)
        return order
