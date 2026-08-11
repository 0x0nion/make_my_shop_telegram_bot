from aiogram import Router
from .payment_proof import user_payment_router

user_payment_group_router = Router()

user_payment_group_router.include_routers(
    user_payment_router
)