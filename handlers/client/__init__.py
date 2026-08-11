from aiogram import Router

from .order_reply import client_reply_router
from .payment import user_payment_group_router
from .cart import user_cart_group_router
from .order import user_order_group_router
from .shop import user_shop_group_router
from .main import client_main_router

client_group_router = Router()

# Порядок регистраций: специализированные FSM-хендлеры (оплата) -> работа с корзиной/заказами -> каталог -> главная
client_group_router.include_routers(
    user_payment_group_router,
    user_order_group_router,
    user_cart_group_router,
    user_shop_group_router,
    client_reply_router,
    client_main_router,
)