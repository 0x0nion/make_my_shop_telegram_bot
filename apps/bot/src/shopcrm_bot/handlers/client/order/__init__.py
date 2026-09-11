# handlers/client/order/__init__.py
from aiogram import Router

from shopcrm_bot.handlers.client.order.order import user_order_router

user_order_group_router = Router()

user_order_group_router.include_routers(
    user_order_router,
)
