"""Тесты расчёта стоимости заказа при создании из корзины."""
import pytest
from sqlalchemy import select

from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import Order, OrderItem
from shopcrm_core.constants import OrderStatus


class TestCreateOrderFromCart:
    """create_order_from_cart: расчёт total_price, очистка корзины, статус."""

    async def test_total_price_single_item(self, repo, session, user_a, product_a):
        """Один товар, qty=3 → total = price * 3."""
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=3))
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order is not None
        assert float(order.total_price) == pytest.approx(30.0)

    async def test_total_price_multiple_items(self, repo, session, user_a, product_a, product_b):
        """2×Widget(10.00) + 1×Gadget(25.50) = 45.50."""
        session.add_all([
            CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),
            CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),
        ])
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order is not None
        assert float(order.total_price) == pytest.approx(45.50)

    async def test_order_items_match_cart(self, repo, session, user_a, product_a, product_b):
        """OrderItem-ы сохраняются с корректными qty и price_at_purchase."""
        session.add_all([
            CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),
            CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),
        ])
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order is not None
        assert len(order.items) == 2

        item_map = {item.product_id: item for item in order.items}
        assert item_map[product_a.id].quantity == 2
        assert float(item_map[product_a.id].price_at_purchase) == pytest.approx(10.00)
        assert item_map[product_b.id].quantity == 1
        assert float(item_map[product_b.id].price_at_purchase) == pytest.approx(25.50)

    async def test_cart_cleared_after_order(self, repo, session, user_a, product_a):
        """После создания заказа корзина пуста."""
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))
        await session.commit()

        await repo.create_order_from_cart(user_id=user_a.id)

        remaining = await session.execute(
            select(CartItem).where(CartItem.user_id == user_a.id)
        )
        assert remaining.scalars().all() == []

    async def test_order_status_is_pending(self, repo, session, user_a, product_a):
        """Новый заказ: status=pending, is_paid=False."""
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order.status == OrderStatus.PENDING.value
        assert order.is_paid is False

    async def test_empty_cart_returns_none(self, repo, user_a):
        """Пустая корзина → None."""
        order = await repo.create_order_from_cart(user_id=user_a.id)
        assert order is None

    async def test_nonexistent_user_returns_none(self, repo):
        """Несуществующий пользователь → None."""
        order = await repo.create_order_from_cart(user_id=99999)
        assert order is None

    async def test_delivery_fields_saved(self, repo, session, user_a, product_a):
        """Адрес и комментарий сохраняются в заказе."""
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))
        await session.commit()

        order = await repo.create_order_from_cart(
            user_id=user_a.id,
            delivery_address="ул. Ленина, 1",
            delivery_address_type="text",
            user_comment="Позвонить заранее",
        )

        assert order.delivery_address == "ул. Ленина, 1"
        assert order.delivery_address_type == "text"
        assert order.user_comment == "Позвонить заранее"
