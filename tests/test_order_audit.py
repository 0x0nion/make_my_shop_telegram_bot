"""Тесты аудита смены статусов заказа (order_status_history + поля аудита).

Проверяют:
  - смена статуса админом фиксируется в журнале (кто/из чего/в что);
  - переход в оплаченный статус выставляет paid_at/paid_by;
  - completed/cancelled выставляют completed_at/cancelled_at;
  - mark_order_paid выставляет is_paid + paid_at/paid_by;
  - отмена клиентом фиксируется в журнале с причиной.
"""
from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import OrderStatusHistory
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.db.repositories.user_repo import UserRepository
from sqlalchemy import select


async def _create_order(repo: UserRepository, session, user, product):
    """Создаёт заказ для user через корзину (обходит проверку остатка)."""
    session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
    await session.commit()
    order = await repo.create_order_from_cart(user_id=user.id)
    assert order is not None
    return order


async def _history(session, order_id: int) -> list[OrderStatusHistory]:
    result = await session.execute(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order_id)
    )
    return list(result.scalars().all())


class TestChangeOrderStatus:
    async def test_records_history(self, session, user_a, user_b, product_a):
        """Смена статуса админом фиксируется в журнале."""
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        await admin.change_order_status(order.id, OrderStatus.PROCESSING.value, changed_by=user_b.id)

        rows = await _history(session, order.id)
        assert len(rows) == 1
        assert rows[0].old_status == OrderStatus.PENDING.value
        assert rows[0].new_status == OrderStatus.PROCESSING.value
        assert rows[0].changed_by == user_b.id

    async def test_paid_status_sets_paid_at(self, session, user_a, user_b, product_a):
        """Переход в оплаченный статус выставляет paid_at/paid_by."""
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        updated = await admin.change_order_status(order.id, OrderStatus.PROCESSING.value, changed_by=user_b.id)
        assert updated.paid_at is not None
        assert updated.paid_by == user_b.id

    async def test_completed_sets_completed_at(self, session, user_a, user_b, product_a):
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        updated = await admin.change_order_status(order.id, OrderStatus.COMPLETED.value, changed_by=user_b.id)
        assert updated.completed_at is not None

    async def test_cancelled_sets_cancelled_at(self, session, user_a, user_b, product_a):
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        updated = await admin.change_order_status(order.id, OrderStatus.CANCELLED.value, changed_by=user_b.id)
        assert updated.cancelled_at is not None

    async def test_same_status_no_history(self, session, user_a, user_b, product_a):
        """Смена на тот же статус — запись в журнал не добавляется."""
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        await admin.change_order_status(order.id, OrderStatus.PENDING.value, changed_by=user_b.id)
        rows = await _history(session, order.id)
        assert len(rows) == 0

    async def test_nonexistent_order_returns_none(self, session, user_b):
        admin = AdminRepository(session)
        result = await admin.change_order_status(999_999, OrderStatus.PROCESSING.value, changed_by=user_b.id)
        assert result is None

    async def test_preserves_pending_modifications(self, session, user_a, user_b, product_a):
        """Изменения на объекте заказа (is_paid/чек) коммитятся вместе со сменой статуса.

        Имитирует process_reject_payment: у заказа есть чек (is_paid/proof заданы),
        админ сбрасывает их на том же объекте (identity map), затем
        change_order_status коммитит всё одной транзакцией.
        """
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        # Исходное состояние: клиент отправил чек, заказ ждёт подтверждения.
        order.is_paid = True
        order.payment_proof_type = "photo"
        order.payment_proof = "hash123"
        order.status = OrderStatus.AWAITING_CONFIRMATION.value
        await session.commit()

        # Отклонение: сбрасываем is_paid/чек на том же объекте, меняем статус.
        order.is_paid = False
        order.payment_proof_type = None
        order.payment_proof = None
        await admin.change_order_status(order.id, OrderStatus.PAYMENT_REQUESTED.value, changed_by=user_b.id)

        fresh = await admin.get_order_by_id(order.id)
        assert fresh.is_paid is False
        assert fresh.payment_proof_type is None
        assert fresh.payment_proof is None
        assert fresh.status == OrderStatus.PAYMENT_REQUESTED.value


class TestMarkOrderPaid:
    async def test_sets_is_paid_and_audit(self, session, user_a, user_b, product_a):
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)
        admin = AdminRepository(session)

        updated = await admin.mark_order_paid(order.id, changed_by=user_b.id)
        assert updated.is_paid is True
        assert updated.paid_at is not None
        assert updated.paid_by == user_b.id


class TestClientCancelRecordsHistory:
    async def test_cancel_records_history_with_reason(self, session, user_a, product_a):
        """Отмена клиентом фиксируется в журнале с причиной."""
        repo = UserRepository(session)
        order = await _create_order(repo, session, user_a, product_a)

        await repo.cancel_order(order.id, user_a.id)

        rows = await _history(session, order.id)
        assert len(rows) == 1
        assert rows[0].new_status == OrderStatus.CANCELLED.value
        assert rows[0].changed_by == user_a.id
        assert rows[0].reason == "client_cancelled"
