from aiogram import Router

from shopcrm_bot.handlers.admin.orders.contact import order_contact_router
from shopcrm_bot.handlers.admin.orders.list import orders_list_router
from shopcrm_bot.handlers.admin.orders.order_payment_request import admin_payment_request_router
from shopcrm_bot.handlers.admin.orders.select_product import order_catalog_router
from shopcrm_bot.handlers.admin.orders.status import order_status_router
from shopcrm_bot.handlers.admin.orders.view import order_view_router
from shopcrm_bot.handlers.admin.orders.items import order_items_router
from shopcrm_bot.handlers.admin.orders.edits import order_edits_router

admin_orders_group_router = Router()

# Подключение модульных роутеров заказов
admin_orders_group_router.include_routers(
    orders_list_router,
    order_view_router,
    order_items_router,
    order_edits_router,
    order_catalog_router,
    order_status_router,
    admin_payment_request_router,
    order_contact_router
)
