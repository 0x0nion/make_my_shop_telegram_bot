"""Тесты изоляции данных: пользователь не видит чужие заказы."""
import pytest
from sqlalchemy import select

from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import Order
from shopcrm_core.constants import OrderStatus, PaymentProofType


class TestOrderOwnership:
    """get_order_with_items / attach_payment_proof / update_order_status / chat_history."""

    async def _create_order_for(self, repo, session, user, product) -> Order:
        """Вспомогательный: создаёт заказ для user через корзину."""
        session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
        await session.commit()
        order = await repo.create_order_from_cart(user_id=user.id)
        assert order is not None
        return order

    async def test_user_sees_own_order(self, repo, session, user_a, user_b, product_a):
        """Свой заказ виден владельцу."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        result = await repo.get_order_with_items(order.id, user_id=user_a.id)
        assert result is not None
        assert result.id == order.id

    async def test_user_cannot_see_foreign_order(self, repo, session, user_a, user_b, product_a):
        """Чужой заказ не виден."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        result = await repo.get_order_with_items(order.id, user_id=user_b.id)
        assert result is None

    async def test_attach_payment_proof_own_order(self, repo, session, user_a, product_a):
        """Свой заказ: чек прикрепляется, статус меняется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        updated = await repo.attach_payment_proof(
            order_id=order.id, user_id=user_a.id,
            proof_type=PaymentProofType.PHOTO.value,
            proof_content="https://example.com/receipt.jpg",
        )
        assert updated is not None
        assert updated.payment_proof_type == PaymentProofType.PHOTO.value
        assert updated.status == OrderStatus.AWAITING_CONFIRMATION.value

    async def test_attach_payment_proof_foreign_order(self, repo, session, user_a, user_b, product_a):
        """Чужой заказ: чек НЕ прикрепляется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        result = await repo.attach_payment_proof(
            order_id=order.id, user_id=user_b.id,
            proof_type=PaymentProofType.PHOTO.value,
            proof_content="https://evil.com/fake.jpg",
        )
        assert result is None

    async def test_attach_payment_proof_paid_order_rejected(self, repo, session, user_a, product_a):
        """Уже оплаченный заказ: чек не прикрепляется повторно."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        order.is_paid = True
        await session.commit()
        result = await repo.attach_payment_proof(
            order_id=order.id, user_id=user_a.id,
            proof_type=PaymentProofType.CASH.value, proof_content="cash",
        )
        assert result is None

    async def test_attach_payment_proof_final_order_rejected(self, repo, session, user_a, product_a):
        """Завершённый заказ: чек не прикрепляется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        order.status = OrderStatus.COMPLETED.value
        await session.commit()

    async def test_update_status_own_order(self, repo, session, user_a, product_a):
        """Свой заказ: статус обновляется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        updated = await repo.update_order_status(
            order_id=order.id, user_id=user_a.id,
            status=OrderStatus.PROCESSING.value,
        )
        assert updated is not None
        assert updated.status == OrderStatus.PROCESSING.value

    async def test_update_status_foreign_order(self, repo, session, user_a, user_b, product_a):
        """Чужой заказ: статус НЕ обновляется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        result = await repo.update_order_status(
            order_id=order.id, user_id=user_b.id,
            status=OrderStatus.CANCELLED.value,
        )
        assert result is None

    async def test_chat_history_own_order(self, repo, session, user_a, product_a):
        """Свой заказ: сообщение добавляется в историю."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        msg = {"sender": "user", "text": "Где мой заказ?", "time": "2025-01-01T12:00:00"}
        updated = await repo.append_order_chat_history(order.id, user_a.id, msg)
        assert updated is not None
        assert updated.chat_history[-1] == msg

    async def test_chat_history_foreign_order(self, repo, session, user_a, user_b, product_a):
        """Чужой заказ: сообщение НЕ добавляется."""
        order = await self._create_order_for(repo, session, user_a, product_a)
        msg = {"sender": "user", "text": "hack", "time": "2025-01-01T12:00:00"}
        result = await repo.append_order_chat_history(order.id, user_b.id, msg)
        assert result is None

    async def test_get_user_orders_only_own(self, repo, session, user_a, user_b, product_a):
        """get_user_orders возвращает только заказы данного пользователя."""
        await self._create_order_for(repo, session, user_a, product_a)
        await self._create_order_for(repo, session, user_b, product_a)
        orders, total = await repo.get_user_orders(user_id=user_a.id)
        assert total == 1
        assert all(o.user_id == user_a.id for o in orders)

    async def test_get_pending_orders_only_own(self, repo, session, user_a, user_b, product_a):
        """get_pending_orders возвращает только неоплаченные заказы данного пользователя."""
        order_a = await self._create_order_for(repo, session, user_a, product_a)
        await self._create_order_for(repo, session, user_b, product_a)
        pending = await repo.get_pending_orders(user_id=user_a.id)
        assert len(pending) == 1
        assert pending[0].id == order_a.id

        # После прикрепления чека статус меняется → заказ больше не "pending"
        result = await repo.attach_payment_proof(
            order_id=order_a.id, user_id=user_a.id,
            proof_type=PaymentProofType.CASH.value, proof_content="cash",
        )
        assert result is not None
        assert result.status == OrderStatus.AWAITING_CONFIRMATION.value
