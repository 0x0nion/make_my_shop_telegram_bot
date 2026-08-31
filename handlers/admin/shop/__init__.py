# handlers/admin/shop/__init__.py
from aiogram import Router

from handlers.admin.shop.catalog import admin_catalog_router
from handlers.admin.shop.main import admin_shop_main_router
from handlers.admin.shop.payment_details_editor import payment_details_editor_router
from handlers.admin.shop.product_editor import editor_router
from handlers.admin.shop.welcome_editor import welcome_editor_router

admin_shop_group_router = Router()

admin_shop_group_router.include_routers(
    admin_shop_main_router,
    admin_catalog_router,
    editor_router,
    welcome_editor_router,
    payment_details_editor_router
)