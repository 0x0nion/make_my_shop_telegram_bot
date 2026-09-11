from typing import Any
from sqlalchemy.orm import selectinload

from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class UserAccountMixin:

    @property
    def _user_repo(self) -> BaseRepository[User]:
        return BaseRepository(User, self.session)

    async def get_user(self, user_id: int) -> User | None:
        return await self._user_repo.get_by_id(user_id)

    async def get_user_with_cart(self, user_id: int) -> User | None:
        options = [
            selectinload(User.cart),
            selectinload(User.orders)
        ]
        return await self._user_repo.get_by_id(user_id, options=options)

    async def create_user(self, user_id: int) -> User:
        logger.info(f"Creating user id={user_id}")
        await self._user_repo.create(id=user_id)
        # Гарантируем, что созданный юзер вернется с инициализированными связями
        user = await self.get_user_with_cart(user_id)
        return user if user else await self.get_user(user_id)

    async def update_language(self, user_id: int, language: str) -> User | None:
        logger.info(f"Updating language for user id={user_id} to '{language}'")
        await self._user_repo.update(user_id, language=language)
        # Подтягиваем актуальный state после коммита
        return await self.get_user_with_cart(user_id)

    async def get_or_create_user(self, tg_user: Any) -> User | None:
        """
        Получает пользователя со связанной корзиной и заказами.
        Если его нет в БД — создает и сразу возвращает со всеми подгруженными связями.
        """
        if not tg_user:
            return None

        user = await self.get_user_with_cart(tg_user.id)
        if not user:
            user = await self.create_user(user_id=tg_user.id)

        return user