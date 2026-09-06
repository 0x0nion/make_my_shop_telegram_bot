# handlers/admin/__init__.py
from aiogram import Router

from shopcrm_bot.filters.admin import IsAdminFilter
from .main import admin_main_router
from .orders import admin_orders_group_router
from .shop import admin_shop_group_router

admin_group_router = Router()
admin_group_router.message.filter(IsAdminFilter())
admin_group_router.callback_query.filter(IsAdminFilter())

admin_group_router.include_routers(
    admin_shop_group_router,
    admin_orders_group_router,
    admin_main_router,
)