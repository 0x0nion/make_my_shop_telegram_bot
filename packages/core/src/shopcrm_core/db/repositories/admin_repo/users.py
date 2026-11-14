# database/repositories/admin_repo/users.py

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.base_repo import BaseRepository


class AdminUsersMixin:

    def _get_user_repo(self) -> BaseRepository[User]:
        """Вспомогательный метод получения базового репозитория пользователей."""
        return BaseRepository(User, self.session)

    async def get_users_count(self) -> int:
        """Возвращает общее количество пользователей в БД."""
        stmt = select(func.count(User.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_users_page(
            self,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[User]:
        """Страница пользователей с подгрузкой заказов (для счётчика в списке).

        Сортировка по id asc — стабильный «порядок добавления»,
        чтобы при in-place редактировании сообщения кнопки не «перемешивались».
        """
        repo = self._get_user_repo()
        return await repo.get_all(
            options=[selectinload(User.orders)],
            order_by=User.id.asc(),
            limit=limit,
            offset=offset,
        )

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Получение одного пользователя по ID (с подгрузкой заказов).

        Заказы нужны для карточки: количество, сумма и активные заказы.
        """
        repo = self._get_user_repo()
        return await repo.get_by_id(user_id, options=[selectinload(User.orders)])

    async def set_user_discount(self, user_id: int, discount: float) -> User | None:
        """Установка персональной скидки пользователя (в процентах, 0–100).

        :return: обновлённый пользователь или None, если не найден.
        """
        repo = self._get_user_repo()
        user = await repo.get_by_id(user_id)
        if not user:
            return None
        user.discount = discount
        await self.session.commit()
        await self.session.refresh(user)
        return user
