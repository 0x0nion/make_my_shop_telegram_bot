from aiogram import Router

from shopcrm_bot.handlers.admin.users.card import user_card_router
from shopcrm_bot.handlers.admin.users.list import users_list_router

admin_users_router = Router()

# Подключение модульных роутеров раздела «Юзеры»
admin_users_router.include_routers(
    users_list_router,
    user_card_router,
)
