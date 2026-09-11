# handlers/client/order/order.py
import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models import User
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_bot.locales import Locale
from shopcrm_bot.services.notification_service import notify_admins_about_cancellation
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)
user_order_router = Router()

# Количество заказов на одной странице списка
ORDERS_PER_PAGE = 10


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
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"[ORDER HANDLER] Invalid page callback: {callback.data}")
        await callback.answer()
        return
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

    try:
        order_id = int(callback.data.split("_")[-1])
    except (IndexError, ValueError):
        logger.warning(f"[ORDER HANDLER] Invalid order callback: {callback.data}")
        await callback.answer()
        return

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
    )
    reply_markup = kb_manager.get_client_order_detail_kb(
        order_id=order.id,
        cancellable=OrderStatus.is_cancellable_by_client(order.status),
    )

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@user_order_router.callback_query(F.data.startswith("client_order_cancel:"))
async def confirm_cancel_order(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
):
    """Показывает подтверждение отмены заказа (только для отменяемых статусов)."""
    locale = Locale(user.language)

    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"[ORDER HANDLER] Invalid cancel callback: {callback.data}")
        await callback.answer()
        return

    order = await user_repo.get_order_with_items(order_id, user.id)
    if not order:
        await callback.answer(
            text=locale.get_text("client.user_order_not_found"),
            show_alert=True,
        )
        return

    if not OrderStatus.is_cancellable_by_client(order.status):
        await callback.answer(
            text=locale.get_text("client.order_cancel_denied"),
            show_alert=True,
        )
        return

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=locale.get_text("client.cancel_order_confirm_yes"),
            callback_data=f"client_order_cancel_confirm:{order_id}",
        ),
        InlineKeyboardButton(
            text=locale.get_text("client.cancel_order_confirm_no"),
            callback_data=f"view_details_order_{order_id}",
        ),
    ]])

    await UIManager.show(
        event=callback,
        text=locale.get_text("client.cancel_order_confirm_prompt", order_id=order_id),
        reply_markup=confirm_kb,
    )


@user_order_router.callback_query(F.data.startswith("client_order_cancel_confirm:"))
async def do_cancel_order(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
    bot: Bot,
    admin_ids: list[int],
):
    """Отменяет заказ, уведомляет администраторов и перерисовывает карточку."""
    locale = Locale(user.language)

    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        logger.warning(f"[ORDER HANDLER] Invalid cancel confirm callback: {callback.data}")
        await callback.answer()
        return

    order = await user_repo.cancel_order(order_id, user.id)
    if not order:
        await callback.answer(
            text=locale.get_text("client.order_cancel_denied"),
            show_alert=True,
        )
        return

    await callback.answer(
        text=locale.get_text("client.order_cancelled", order_id=order_id),
        show_alert=True,
    )

    # Уведомляем администраторов в фоне (не блокируем ответ клиенту)
    asyncio.create_task(
        notify_admins_about_cancellation(bot=bot, order_id=order_id, admin_ids=admin_ids)
    )

    # Перерисовываем карточку заказа (кнопка отмены уже не показывается)
    text = locale.format_order(order, template_key="client.user_order_details")
    reply_markup = locale.keyboards.get_client_order_detail_kb(
        order_id=order.id,
        cancellable=False,
    )
    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )