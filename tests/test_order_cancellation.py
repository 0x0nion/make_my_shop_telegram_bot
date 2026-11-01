"""Тесты отмены заказа клиентом: допустимые статусы, запрещённые статусы, изоляция владельца."""
import pytest
from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import Order


class TestIsCancellableByClient:
    """OrderStatus.is_cancellable_by_client — единый источник истины для отмены клиентом."""

    @pytest.mark.parametrize("status", [
        OrderStatus.PENDING,
        OrderStatus.PAYMENT_REQUESTED,
        OrderStatus.AWAITING_CONFIRMATION,
        OrderStatus.PAYMENT_REJECTED,
        OrderStatus.PROCESSING,
        OrderStatus.READY_FOR_PICKUP,
        OrderStatus.ON_HOLD,
    ])
    def test_cancellable_statuses(self, status):
        """Заказ можно отменить до передачи курьеру (включая паузу и отклонённый платёж)."""
        assert OrderStatus.is_cancellable_by_client(status.value) is True

    @pytest.mark.parametrize("status", [
        OrderStatus.DELIVERING,
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUND_IN_PROGRESS,
    ])
    def test_non_cancellable_statuses(self, status):
        """Заказ в пути / завершённый / отменённый / с возвратом отменить нельзя."""
        assert OrderStatus.is_cancellable_by_client(status.value) is False


class TestCancelOrder:
    """UserOrderMixin.cancel_order — проверка владельца и статуса."""

    async def _create_order_for(self, repo, session, user, product) -> Order:
        """Вспомогательный: создаёт заказ для user через корзину."""
        session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
        await session.commit()
        order = await repo.create_order_from_cart(user_id=user.id)
        assert order is not None
        return order

    async def test_cancel_own_pending_order(self, repo, session, user_a, product_a):
        """Свой заказ в статусе PENDING: отменяется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        assert order.status == OrderStatus.PENDING.value

        cancelled = await repo.cancel_order(order.id, user_a.id)
        assert cancelled is not None
        assert cancelled.status == OrderStatus.CANCELLED.value

    async def test_cancel_foreign_order_rejected(self, repo, session, user_a, user_b, product_a):
        """Чужой заказ: отменить нельзя, статус не меняется."""
        order = await self._create_order_for(repo, session, user_a, product_a)

        result = await repo.cancel_order(order.id, user_b.id)
        assert result is None

        fresh = await repo.get_order_with_items(order.id, user_a.id)
        assert fresh.status == OrderStatus.PENDING.value

    @pytest.mark.parametrize("status", [
        OrderStatus.DELIVERING,
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUND_IN_PROGRESS,
    ])
    async def test_cancel_non_cancellable_status_rejected(
        self, repo, session, user_a, product_a, status
    ):
        """Заказ в неотменяемом статусе: отмена отклоняется, статус не меняется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        order.status = status.value
        await session.commit()

        result = await repo.cancel_order(order.id, user_a.id)
        assert result is None

        fresh = await repo.get_order_with_items(order.id, user_a.id)
        assert fresh.status == status.value

    async def test_cancel_nonexistent_order(self, repo, session, user_a):
        """Несуществующий заказ: возвращается None."""
        result = await repo.cancel_order(999_999, user_a.id)
        assert result is None
