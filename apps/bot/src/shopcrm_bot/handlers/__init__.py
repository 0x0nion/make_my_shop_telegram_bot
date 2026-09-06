from aiogram import Router
from shopcrm_bot.handlers.admin import admin_group_router
from shopcrm_bot.handlers.client import client_group_router

routers = Router()
routers.include_routers(
    admin_group_router,
    client_group_router,
)