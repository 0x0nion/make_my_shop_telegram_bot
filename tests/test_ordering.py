"""Тесты стабильного порядка элементов (корзина / позиции заказа).

Регрессия: без order_by на relationship порядок элементов недетерминированный,
и при in-place редактировании сообщения кнопки «перемешивались».
Теперь User.cart и Order.items всегда отсортированы по id (порядок добавления).
"""
from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import Order
from shopcrm_core.db.models.user import User


def _order_by_ids(prop) -> list:
    """Возвращает имена колонок из order_by relationship (для проверки)."""
    order_by = prop.order_by
    assert order_by, "relationship должен иметь order_by"
    return [c.name for c in order_by if hasattr(c, "name")]


class TestRelationshipOrdering:
    """order_by на relationship гарантирует стабильный порядок по id."""

    def test_cart_relationship_orders_by_id(self):
        """Связь User.cart отсортирована по CartItem.id."""
        assert "id" in _order_by_ids(User.cart.property)

    def test_order_items_relationship_orders_by_id(self):
        """Связь Order.items отсортирована по OrderItem.id."""
        assert "id" in _order_by_ids(Order.items.property)


class TestCartOrdering:
    """Корзина возвращается в порядке добавления (по id)."""

    async def test_cart_items_in_id_order(self, repo, session, user_a, product_a, product_b):
        """После перезагрузки корзина в порядке id (порядок добавления)."""
        # Добавляем в «перемешанном» порядке: сначала product_b, потом product_a
        session.add_all([
            CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),
            CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),
        ])
        await session.commit()

        user = await repo.get_cart_with_products(user_id=user_a.id)
        assert user is not None
        assert len(user.cart) == 2

        ids = [item.id for item in user.cart]
        assert ids == sorted(ids), "Корзина должна быть в порядке id"
        # Первый добавленный (product_b) — с меньшим id
        assert user.cart[0].product_id == product_b.id
        assert user.cart[1].product_id == product_a.id


class TestOrderItemsOrdering:
    """Позиции заказа возвращаются в порядке добавления (по id)."""

    async def test_order_items_in_id_order(self, repo, session, user_a, product_a, product_b):
        """Позиции заказа в порядке id после создания из корзины."""
        session.add_all([
            CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),
            CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),
        ])
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)
        assert order is not None
        assert len(order.items) == 2

        ids = [item.id for item in order.items]
        assert ids == sorted(ids), "Позиции заказа должны быть в порядке id"
