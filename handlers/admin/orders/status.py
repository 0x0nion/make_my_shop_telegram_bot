import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from src.core.ui import UIManager

logger = logging.getLogger(__name__)

order_status_router = Router()


@order_status_router.callback_query(F.data.startswith("admin_order_change_status:"))
async def process_change_status_menu(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Открывает подменю выбора нового статуса заказа (PROCESSING, DELIVERING, CANCELLED).
    Callback format: admin_order_change_status:{order_id}:{status}:{page}
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    # Получаем локализованный текст через get_text
    prompt_text = kb.get_text(
        "order_status_prompt",
        f"🔄 <b>Изменение статуса заказа #{order_id}</b>\n\nВыберите новый статус из списка:"
    )
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
    Callback format: admin_order_set_status:{order_id}:{new_status}:{filter_status}:{page}
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    new_status = parts[2]
    filter_status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # Обновляем статус
    order.status = new_status
    await admin_repo.update_order(order)

    await callback.answer(f"✅ Статус заказа успешно изменен на: {new_status}", show_alert=True)

    # Возвращаем в подробную карточку заказа (UIManager уже задействован внутри render_order_detail)
    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=filter_status,
        page=page,
    )