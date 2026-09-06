# handlers/client/cart/__init__.py
from aiogram import Router

from shopcrm_bot.handlers.client.cart.cart import user_cart_router

user_cart_group_router = Router()

user_cart_group_router.include_routers(
    user_cart_router,
)
