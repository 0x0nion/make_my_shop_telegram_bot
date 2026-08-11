import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from src.core.ui import UIManager
from state.admin_states import AdminOrderState

logger = logging.getLogger(__name__)

order_edits_router = Router()


# ---------------------------------------------------------------------
# РЕДАКТИРОВАНИЕ АДРЕСА
# ---------------------------------------------------------------------

@order_edits_router.callback_query(F.data.startswith("admin_order_edit_addr:"))
async def start_edit_address(
        callback: CallbackQuery,
        state: FSMContext,
        user: User,
):
    parts = callback.data.split(":")
    order_id, status, page = int(parts[1]), parts[2], int(parts[3])

    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    await state.update_data(
        order_id=order_id,
        status=status,
        page=page,
        last_bot_msg_id=callback.message.message_id,
    )
    await state.set_state(AdminOrderState.edit_address)

    back_callback = f"admin_order_view:{order_id}:{status}:{page}"
    text = kb.get_text(
        "admin_order_messages.prompt_edit_addr",
        "✍️ Введите <b>новый адрес доставки</b> для заказа:"
    )
    reply_markup = kb.get_cancel_add_category_kb(back_callback=back_callback)

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@order_edits_router.message(AdminOrderState.edit_address, F.text)
async def process_edit_address(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
):
    new_address = message.text.strip()
    data = await state.get_data()
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    last_bot_msg_id = data.get("last_bot_msg_id")

    order = await admin_repo.get_order_by_id(order_id)
    if order:
        order.delivery_address = new_address
        await admin_repo.update_order(order)

    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await render_order_detail(
        event=message,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
        message_id_to_edit=last_bot_msg_id,
    )


# ---------------------------------------------------------------------
# РЕДАКТИРОВАНИЕ СТОИМОСТИ ДОСТАВКИ
# ---------------------------------------------------------------------

@order_edits_router.callback_query(F.data.startswith("admin_order_edit_shipping:"))
async def start_edit_shipping(
        callback: CallbackQuery,
        state: FSMContext,
        user: User,
):
    parts = callback.data.split(":")
    order_id, status, page = int(parts[1]), parts[2], int(parts[3])

    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    await state.update_data(
        order_id=order_id,
        status=status,
        page=page,
        last_bot_msg_id=callback.message.message_id,
    )
    await state.set_state(AdminOrderState.edit_shipping_cost)

    back_callback = f"admin_order_view:{order_id}:{status}:{page}"
    text = kb.get_text(
        "admin_order_messages.prompt_edit_shipping",
        "🚚 Введите <b>новую стоимость доставки</b> (число):"
    )
    reply_markup = kb.get_cancel_add_category_kb(back_callback=back_callback)

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@order_edits_router.message(AdminOrderState.edit_shipping_cost, F.text)
async def process_edit_shipping(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
):
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    text_val = message.text.strip().replace(",", ".")
    try:
        new_cost = float(text_val)
        if new_cost < 0:
            raise ValueError
    except ValueError:
        err_msg = kb.get_text(
            "admin_order_messages.invalid_number",
            "❌ Введите корректное положительное число."
        )
        await message.answer(err_msg)
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    last_bot_msg_id = data.get("last_bot_msg_id")

    order = await admin_repo.get_order_by_id(order_id)
    if order:
        order.delivery_price = new_cost

        # Пересчитываем итоговую стоимость (товары + новая доставка)
        items_sum = sum(i.quantity * float(i.price_at_purchase) for i in order.items) if order.items else 0.0
        order.total_price = items_sum + new_cost

        await admin_repo.update_order(order)

    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await render_order_detail(
        event=message,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
        message_id_to_edit=last_bot_msg_id,
    )


# ---------------------------------------------------------------------
# ДОБАВЛЕНИЕ / РЕДАКТИРОВАНИЕ КОММЕНТАРИЯ МЕНЕДЖЕРА
# ---------------------------------------------------------------------

@order_edits_router.callback_query(F.data.startswith("admin_order_edit_comment:"))
async def start_edit_comment(
        callback: CallbackQuery,
        state: FSMContext,
        user: User,
):
    parts = callback.data.split(":")
    order_id, status, page = int(parts[1]), parts[2], int(parts[3])

    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    await state.update_data(
        order_id=order_id,
        status=status,
        page=page,
        last_bot_msg_id=callback.message.message_id,
    )
    await state.set_state(AdminOrderState.edit_admin_comment)

    back_callback = f"admin_order_view:{order_id}:{status}:{page}"
    text = kb.get_text(
        "admin_order_messages.prompt_edit_comment",
        "💬 Введите <b>комментарий к заказу</b> (виден только администраторам):"
    )
    reply_markup = kb.get_cancel_add_category_kb(back_callback=back_callback)

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@order_edits_router.message(AdminOrderState.edit_admin_comment, F.text)
async def process_edit_comment(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
):
    new_comment = message.text.strip()
    data = await state.get_data()
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    last_bot_msg_id = data.get("last_bot_msg_id")

    order = await admin_repo.get_order_by_id(order_id)
    if order:
        order.manager_comment = new_comment
        await admin_repo.update_order(order)

    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await render_order_detail(
        event=message,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
        message_id_to_edit=last_bot_msg_id,
    )