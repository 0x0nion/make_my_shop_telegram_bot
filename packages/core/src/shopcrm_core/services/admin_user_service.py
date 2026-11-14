# src/services/admin_user_service.py
"""Бизнес-логика управления пользователями (админ-раздел «Юзеры»).

Карточка пользователя (сводка по заказам) и персональная скидка.
"""
import logging

from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository

logger = logging.getLogger(__name__)


class AdminUserService:
    """Карточка пользователя и персональная скидка."""

    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    async def get_user_card(self, user_id: int) -> User | None:
        """Получение пользователя для карточки (с подгрузкой заказов)."""
        return await self.admin_repo.get_user_by_id(user_id)

    async def set_user_discount(self, user_id: int, discount: float) -> User | None:
        """Установка персональной скидки (в процентах, 0–100).

        :return: обновлённый пользователь или None, если не найден.
        """
        user = await self.admin_repo.set_user_discount(user_id, discount)
        if user:
            logger.info(
                f"User discount updated: user_id={user_id} discount={discount}%"
            )
        return user
