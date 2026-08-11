# handlers/admin/shop/__init__.py
from aiogram import Router

from handlers.admin.shop.categories import categories_router
from handlers.admin.shop.payment_details_editor import payment_details_editor_router
from handlers.admin.shop.product_editor import editor_router
from handlers.admin.shop.products import products_router
from handlers.admin.shop.welcome_editor import welcome_editor_router

admin_shop_group_router = Router()

admin_shop_group_router.include_routers(
    categories_router,
    products_router,
    editor_router,
    welcome_editor_router,
    payment_details_editor_router
)