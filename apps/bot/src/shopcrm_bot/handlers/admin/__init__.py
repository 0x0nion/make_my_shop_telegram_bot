# handlers/admin/__init__.py
from aiogram import Router

from shopcrm_bot.filters.admin import IsAdminFilter

from .broadcast import broadcast_router
from .main import admin_main_router
from .orders import admin_orders_group_router
from .shop import admin_shop_group_router
from .users import admin_users_router
from .warehouse import warehouse_router
from .workers import admin_workers_router

admin_group_router = Router()
admin_group_router.message.filter(IsAdminFilter())
admin_group_router.callback_query.filter(IsAdminFilter())

admin_group_router.include_routers(
    admin_shop_group_router,
    admin_orders_group_router,
    warehouse_router,
    admin_workers_router,
    admin_users_router,
    broadcast_router,
    admin_main_router,
)