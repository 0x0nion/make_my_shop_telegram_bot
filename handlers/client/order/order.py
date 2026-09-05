# handlers/client/order/order.py
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.models import User
from database.repositories.user_repo import UserRepository
from locales.locale import Locale
from src.core.ui import UIManager

logger = logging.getLogger(__name__)
user_order_router = Router()

# Количество заказов на одной странице списка
ORDERS_PER_PAGE = 10


def _build_buyer_info(locale: Locale, user: User) -> str:
    """Строка покупателя для карточки заказа (username или ID)."""
    if getattr(user, "username", None):
        return locale.get_text("admin.orders.buyer_name", username=user.username, user_id=user.id)
    return locale.get_text("admin.orders.buyer_id", user_id=user.id)


async def _show_orders_page(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
    page: int,
):
    """Показывает страницу списка всех заказов пользователя."""
    locale = Locale(user.language)
    kb_manager = locale.keyboards

    orders, total = await user_repo.get_user_orders(
        user_id=user.id, page=page, per_page=ORDERS_PER_PAGE
    )
    total_pages = max(1, (total + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)
    page = max(1, min(page, total_pages))

    if not orders:
        text = locale.get_text("client.user_empty_orders")
        reply_markup = kb_manager.get_main_kb(
            orders=user.active_orders_count,
            cart=len(getattr(user, "cart", []) or []),
        )
    else:
        text = locale.get_text("client.user_orders_title")
        reply_markup = kb_manager.get_orders_kb(
            orders, page=page, total_pages=total_pages
        )

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@user_order_router.callback_query(F.data == "client_orders")
async def show_orders(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
):
    """Отображает список всех заказов пользователя (первая страница)."""
    await _show_orders_page(callback, user_repo, user, page=1)


@user_order_router.callback_query(F.data.startswith("client_orders_page:"))
async def show_orders_page(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
):
    """Пагинация списка заказов пользователя."""
    page = int(callback.data.split(":")[1])
    await _show_orders_page(callback, user_repo, user, page=page)


@user_order_router.callback_query(F.data.startswith("view_details_order_"))
async def view_order_details(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
):
    """Отображает подробную информацию по конкретному заказу."""
    locale = Locale(user.language)
    kb_manager = locale.keyboards

    order_id = int(callback.data.split("_")[-1])
    order = await user_repo.get_order_with_items(order_id, user.id)

    if not order:
        await callback.answer(
            text=locale.get_text("client.user_order_not_found"),
            show_alert=True,
        )
        return

    text = locale.format_order(
        order,
        template_key="client.user_order_details",
        buyer_info=_build_buyer_info(locale, user),
    )
    reply_markup = kb_manager.get_kb("back_to_orders")

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )