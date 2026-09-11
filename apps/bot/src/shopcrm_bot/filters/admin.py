from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message
from shopcrm_bot.config import config


class IsAdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user and user.id in config.ADMIN_ID)

