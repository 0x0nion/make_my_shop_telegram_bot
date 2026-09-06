import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_bot.handlers.admin.orders.common import render_order_detail
from shopcrm_bot.locales import Locale
from shopcrm_core.constants import ORDER_STATUS_BY_CODE, ORDER_STATUS_CODES, OrderStatus
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)

order_status_router = Router()


@order_status_router.callback_query(F.data.startswith("admin_order_change_status:"))
async def process_change_status_menu(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Открывает подменю выбора нового статуса заказа (все статусы из enum OrderStatus).
    Callback format: admin_order_change_status:{order_id}:{status}:{page}
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    lang = user.language
    locale = Locale(lang)
    kb = locale.keyboards

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer(locale.get_text("admin.orders.order_not_found"), show_alert=True)
        return

    # Получаем локализованный текст через get_text
    prompt_text = locale.get_text("admin.orders.status_prompt")
    if "{order_id}" in prompt_text:
        prompt_text = prompt_text.format(order_id=order_id)

    reply_markup = kb.get_order_status_kb(
        order_id=order_id,
        status=status,
        page=page,
    )

    # Используем UIManager для отрисовки меню выбора статуса
    await UIManager.show(
        event=callback,
        text=prompt_text,
        reply_markup=reply_markup,
    )


@order_status_router.callback_query(F.data.startswith("admin_order_set_status:"))
async def process_set_order_status(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Применяет выбранный статус к заказу и возвращает в карточку.
    Callback format: admin_order_set_status:{order_id}:{new_status_code}:{filter_status_code}:{page}
    (статусы передаются короткими кодами из ORDER_STATUS_CODES — лимит callback_data 64 байта;
    для обратной совместимости принимаются и полные имена статусов).
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    new_status = ORDER_STATUS_BY_CODE.get(parts[2], parts[2])
    filter_status = ORDER_STATUS_BY_CODE.get(parts[3], parts[3]) if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    locale = Locale(user.language)

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer(locale.get_text("admin.orders.order_not_found"), show_alert=True)
        return

    # Закрытие неоплаченного заказа: сначала просим подтвердить получение оплаты
    # (актуально для наличных — is_paid ставится только вручную админом).
    if new_status == OrderStatus.COMPLETED.value and not order.is_paid:
        prompt_text = locale.get_text("admin.orders.close_confirm_prompt").format(order_id=order_id)
        # Фильтр кодируем коротким кодом, чтобы callback не превысил 64 байта.
        filter_code = ORDER_STATUS_CODES.get(filter_status, filter_status)
        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=locale.get_text("admin.orders.close_confirm_yes"),
                        callback_data=f"admin_order_close_confirm:{order_id}:paid:{filter_code}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=locale.get_text("admin.orders.close_confirm_no"),
                        callback_data=f"admin_order_close_confirm:{order_id}:unpaid:{filter_code}:{page}",
                    ),
                ]
            ]
        )
        await UIManager.show(
            event=callback,
            text=prompt_text,
            reply_markup=confirm_kb,
        )
        return

    # Обновляем статус
    order.status = new_status
    await admin_repo.update_order(order)

    await callback.answer(
        locale.get_text("admin.orders.status_changed", status=new_status),
        show_alert=True,
    )

    # Возвращаем в подробную карточку заказа (UIManager уже задействован внутри render_order_detail)
    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=filter_status,
        page=page,
    )


@order_status_router.callback_query(F.data.startswith("admin_order_mark_paid:"))
async def process_mark_order_paid(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Отмечает заказ как оплаченный (например, наличные получены от клиента).
    Callback format: admin_order_mark_paid:{order_id}:{status}:{page}
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    locale = Locale(user.language)

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer(locale.get_text("admin.orders.order_not_found"), show_alert=True)
        return

    order.is_paid = True
    await admin_repo.update_order(order)

    await callback.answer(locale.get_text("admin.orders.marked_paid"), show_alert=True)

    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_status_router.callback_query(F.data.startswith("admin_order_close_confirm:"))
async def process_confirm_close_order(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Применяет закрытие заказа после подтверждения получения оплаты.
    Callback format: admin_order_close_confirm:{order_id}:{paid_flag}:{filter_status_code}:{page}
    paid_flag: "paid" | "unpaid"
    (фильтр передаётся коротким кодом из ORDER_STATUS_CODES — лимит callback_data 64 байта;
    для обратной совместимости принимается и полное имя статуса).
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    paid_flag = parts[2] if len(parts) > 2 else "unpaid"
    filter_status = ORDER_STATUS_BY_CODE.get(parts[3], parts[3]) if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    locale = Locale(user.language)

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer(locale.get_text("admin.orders.order_not_found"), show_alert=True)
        return

    order.status = OrderStatus.COMPLETED.value
    if paid_flag == "paid":
        order.is_paid = True
    await admin_repo.update_order(order)

    await callback.answer(
        locale.get_text("admin.orders.status_changed", status=OrderStatus.COMPLETED.value),
        show_alert=True,
    )

    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=filter_status,
        page=page,
    )