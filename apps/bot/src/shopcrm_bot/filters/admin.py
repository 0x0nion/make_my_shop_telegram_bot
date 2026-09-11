from typing import Any, Dict

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message
from shopcrm_bot.config import config


class IsAdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery, data: Dict[str, Any]) -> bool:
        user = event.from_user
        # Админы из workflow data (их ставит DbSessionMiddleware):
        # тенант-специфичные при хостинге, config.ADMIN_ID при self-hosted.
        admin_ids = data.get("admin_ids") or config.ADMIN_ID
        return bool(user and user.id in admin_ids)

