# database/repositories/admin_repo/orders.py

from typing import Sequence
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload

from database.models.order import Order, OrderItem
from database.repositories.base_repo import BaseRepository
from utils.logger import logger


class AdminOrdersMixin:

    def _get_order_repo(self) -> BaseRepository[Order]:
        """Вспомогательный метод получения базового репозитория заказов."""
        return BaseRepository(Order, self.session)

    async def get_orders_count_by_statuses(self) -> dict[str, int]:
        """
        Возвращает словарик с количеством заказов по каждому статусу.
        Пример ответа: {"pending": 5, "processing": 2, "completed": 10}
        """
        stmt = (
            select(Order.status, func.count(Order.id))
            .group_by(Order.status)
        )
        result = await self.session.execute(stmt)
        return dict(result.all())

    async def get_orders_by_status(
            self,
            status: str | None = None,
            limit: int | None = None,
            offset: int | None = None
    ) -> list[Order]:
        """
        Запрашивает все заказы с подгрузкой пользователя и товаров (OrderItem + Product).
        Если status не указан или равен 'all', отдаются все заказы.
        """
        options = [
            joinedload(Order.user),
            selectinload(Order.items).joinedload(OrderItem.product)
        ]

        expressions = []
        if status and status != "all":
            expressions.append(Order.status == status)

        repo = self._get_order_repo()
        return await repo.get_all(
            *expressions,
            options=options,
            order_by=Order.created_at.desc(),
            limit=limit,
            offset=offset
        )

    async def get_new_orders_count(self, status: str = "pending") -> int:
        """
        Возвращает точное количество новых (необработанных) заказов.
        """
        stmt = (
            select(func.count(Order.id))
            .where(Order.status == status)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_order_by_id(self, order_id: int) -> Order | None:
        """
        Получение одного заказа по ID со всеми связанными сущностями (user, items, product).
        """
        options = [
            joinedload(Order.user),
            selectinload(Order.items).joinedload(OrderItem.product)
        ]
        repo = self._get_order_repo()
        return await repo.get_by_id(order_id, options=options)

    async def update_order(self, order: Order) -> Order:
        """
        Универсальный метод обновления заказа.
        Если объект уже находится в сессии, явно коммитим изменения без merge.
        Если объект отсоединён (detached), выполяем merge и обновляем состояние.
        """
        logger.info(f"Updating order id={order.id} (status={order.status}, total_price={order.total_price})")

        if order in self.session:
            await self.session.commit()
            await self.session.refresh(order)
            return order

        updated_order = await self.session.merge(order)
        await self.session.commit()
        await self.session.refresh(updated_order)

        return updated_order

    async def append_order_chat_history(self, order_id: int, message_record: dict) -> Order | None:
        """
        Добавляет новое сообщение в историю чата заказа.
        """
        order = await self.get_order_by_id(order_id)
        if not order:
            return None

        # Инициализируем список, если он пуст/None
        if order.chat_history is None:
            order.chat_history = []

        # Создаем копию списка для корректного отслеживания изменений в SQLAlchemy JSON
        history = list(order.chat_history)
        history.append(message_record)
        order.chat_history = history

        return await self.update_order(order)

    async def clear_order_chat_history(self, order_id: int) -> Order | None:
        """
        Полностью очищает историю переписки по заказу.
        """
        order = await self.get_order_by_id(order_id)
        if not order:
            return None

        order.chat_history = []
        return await self.update_order(order)


