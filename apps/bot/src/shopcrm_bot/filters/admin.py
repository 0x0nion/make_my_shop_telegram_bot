from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from shopcrm_bot.config import config


class IsAdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery, admin_ids: list[int] | None = None) -> bool:
        user = event.from_user
        # Админы из workflow data (их ставит DbSessionMiddleware);
        # по умолчанию — config.ADMIN_ID.
        admin_ids = admin_ids or config.ADMIN_ID
        return bool(user and user.id in admin_ids)

