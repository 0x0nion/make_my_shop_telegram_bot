from sqlalchemy import and_
from sqlalchemy.orm import selectinload, joinedload

from shopcrm_core.db.models import OrderItem, Order
from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.constants import OrderStatus, PaymentProofType
from shopcrm_core.logging import logger


class UserOrderMixin:

    @property
    def _order_repo(self) -> BaseRepository[Order]:
        return BaseRepository(Order, self.session)

    @property
    def _cart_repo(self) -> BaseRepository[CartItem]:
        return BaseRepository(CartItem, self.session)

    async def create_order_from_cart(
            self,
            user_id: int,
            delivery_address: str | None = None,
            delivery_address_type: str | None = None,
            user_comment: str | None = None
    ) -> Order | None:
        logger.info(f"Creating order from cart for user id={user_id}")
        user = await self.get_cart_with_products(user_id)

        if not user or not user.cart:
            return None

        total_price = 0.0
        order_items = []

        for cart_item in user.cart:
            current_price = float(cart_item.product.price)
            total_price += current_price * cart_item.quantity

            order_items.append(
                OrderItem(
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity,
                    price_at_purchase=current_price
                )
            )

        # 1. Создаем заказ с флагом is_paid=False и статусом PENDING
        new_order = await self._order_repo.create_without_commit(
            user_id=user_id,
            total_price=total_price,
            delivery_address=delivery_address,
            delivery_address_type=delivery_address_type,
            user_comment=user_comment,
            is_paid=False,
            status=OrderStatus.PENDING.value,
            items=order_items
        )

        # 2. Очищаем элементы корзины через ORM-удаление объектов
        for item in list(user.cart):
            await self.session.delete(item)

        # 3. Фиксируем транзакцию
        await self.session.commit()

        # 4. Инвалидируем состояние юзера в сессии
        self.session.expire(user)

        # 5. Возвращаем созданный заказ со всеми деталями
        return await self._order_repo.get_by_id(
            new_order.id,
            options=[selectinload(Order.items).joinedload(OrderItem.product)]
        )

    async def get_pending_orders(self, user_id: int) -> list[Order]:
        """Возвращает неоплаченные активные заказы пользователя."""
        return await self._order_repo.get_all(
            and_(
                Order.user_id == user_id,
                Order.is_paid == False,
                Order.status.notin_([OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value])
            ),
            options=[selectinload(Order.items).joinedload(OrderItem.product)],
            order_by=Order.created_at.desc()
        )

    async def get_user_orders(
        self, user_id: int, page: int = 1, per_page: int = 10
    ) -> tuple[list[Order], int]:
        """Возвращает страницу всех заказов пользователя (новые сверху) и общее количество."""
        total = await self._order_repo.count(Order.user_id == user_id)
        orders = await self._order_repo.get_all(
            Order.user_id == user_id,
            order_by=Order.created_at.desc(),
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        return orders, total

    async def get_order_with_items(self, order_id: int, user_id: int) -> Order | None:
        options = [selectinload(Order.items).joinedload(OrderItem.product)]
        return await self._order_repo.get_one(
            and_(
                Order.id == order_id,
                Order.user_id == user_id
            ),
            options=options
        )

    async def attach_payment_proof(
            self,
            order_id: int,
            user_id: int,
            proof_type: str,
            proof_content: str
    ) -> Order | None:
        """
        Прикрепляет подтверждение оплаты к заказу.
        Разрешает прикрепление/переотправку чека, если заказ еще НЕ оплачен (is_paid=False)
        и НЕ отменен/завершен.
        """
        order = await self.get_order_with_items(order_id, user_id)

        # Если заказ не найден, УЖЕ ОПЛАЧЕН или завершен/отменен — отклоняем
        if not order or order.is_paid or OrderStatus.is_final(order.status):
            return None

        order.payment_proof_type = proof_type
        order.payment_proof = proof_content
        order.status = OrderStatus.AWAITING_CONFIRMATION.value

        await self.session.commit()
        return order

    async def update_order_status(
            self,
            order_id: int,
            user_id: int,
            status: str
    ) -> Order | None:
        """Обновляет статус заказа. Проверяет принадлежность заказа пользователю."""
        order = await self.get_order_with_items(order_id, user_id)
        if not order:
            return None
        order.status = status
        await self.session.commit()
        return order

    async def append_order_chat_history(self, order_id: int, user_id: int, message_record: dict) -> Order | None:
        """
        Добавляет новое сообщение в историю чата заказа от имени клиента.
        Проверяет принадлежность заказа конкретному пользователю для безопасности.
        """
        order = await self.get_order_with_items(order_id, user_id)
        if not order:
            return None

        # Инициализируем список, если он пуст/None
        if order.chat_history is None:
            order.chat_history = []

        # Создаем копию списка для корректного отслеживания изменений в SQLAlchemy JSON
        history = list(order.chat_history)
        history.append(message_record)
        order.chat_history = history

        await self.session.commit()
        await self.session.refresh(order)
        return order


    