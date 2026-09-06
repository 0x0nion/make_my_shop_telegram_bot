import logging
from contextlib import suppress
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail
from locales.locale import Locale
from src.core.ui import UIManager
from src.services.address_service import build_location_address, normalize_text_address
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

    lang = user.language
    locale = Locale(lang)
    kb = locale.keyboards

    await state.update_data(
        order_id=order_id,
        status=status,
        page=page,
        last_bot_msg_id=callback.message.message_id,
    )
    await state.set_state(AdminOrderState.edit_address)

    back_callback = f"admin_order_view:{order_id}:{status}:{page}"
    text = locale.get_text("admin.orders.prompt_edit_addr")
    reply_markup = kb.get_back_kb(back_callback)

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@order_edits_router.message(AdminOrderState.edit_address)
async def process_edit_address(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
):
    locale = Locale(user.language)
    kb = locale.keyboards

    data = await state.get_data()
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    last_bot_msg_id = data.get("last_bot_msg_id")
    back_callback = f"admin_order_view:{order_id}:{status}:{page}"

    with suppress(TelegramBadRequest):
        await message.delete()

    if message.location:
        new_address, addr_type = build_location_address(
            message.location.latitude, message.location.longitude
        )
    elif message.text:
        new_address, addr_type = normalize_text_address(message.text)
    else:
        new_address, addr_type = None, None

    if not new_address:
        await UIManager.show(
            event=message,
            text=(
                f"{locale.get_text('admin.orders.prompt_edit_addr')}\n\n"
                f"{locale.get_text('admin.orders.prompt_edit_addr_error')}"
            ),
            reply_markup=kb.get_back_kb(back_callback),
            message_id_to_edit=last_bot_msg_id,
        )
        return

    order = await admin_repo.get_order_by_id(order_id)
    if order:
        order.delivery_address = new_address
        order.delivery_address_type = addr_type
        await admin_repo.update_order(order)

    await state.clear()

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

    lang = user.language
    locale = Locale(lang)
    kb = locale.keyboards

    await state.update_data(
        order_id=order_id,
        status=status,
        page=page,
        last_bot_msg_id=callback.message.message_id,
    )
    await state.set_state(AdminOrderState.edit_shipping_cost)

    back_callback = f"admin_order_view:{order_id}:{status}:{page}"
    text = locale.get_text("admin.orders.prompt_edit_shipping")
    reply_markup = kb.get_back_kb(back_callback)

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
    lang = user.language
    locale = Locale(lang)
    kb = locale.keyboards

    data = await state.get_data()
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    last_bot_msg_id = data.get("last_bot_msg_id")
    back_callback = f"admin_order_view:{order_id}:{status}:{page}"

    with suppress(TelegramBadRequest):
        await message.delete()

    text_val = message.text.strip().replace(",", ".")
    try:
        new_cost = float(text_val)
        if new_cost < 0:
            raise ValueError
    except ValueError:
        await UIManager.show(
            event=message,
            text=locale.get_text("admin.orders.invalid_number"),
            reply_markup=kb.get_back_kb(back_callback),
            message_id_to_edit=last_bot_msg_id,
        )
        return

    order = await admin_repo.get_order_by_id(order_id)
    if order:
        order.delivery_price = new_cost

        # Пересчитываем итоговую стоимость (товары + новая доставка)
        items_sum = sum(i.quantity * float(i.price_at_purchase) for i in order.items) if order.items else 0.0
        order.total_price = items_sum + new_cost

        await admin_repo.update_order(order)

    await state.clear()

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

    lang = user.language
    locale = Locale(lang)
    kb = locale.keyboards

    await state.update_data(
        order_id=order_id,
        status=status,
        page=page,
        last_bot_msg_id=callback.message.message_id,
    )
    await state.set_state(AdminOrderState.edit_admin_comment)

    back_callback = f"admin_order_view:{order_id}:{status}:{page}"
    text = locale.get_text("admin.orders.prompt_edit_comment")
    reply_markup = kb.get_back_kb(back_callback)

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

    with suppress(TelegramBadRequest):
        await message.delete()

    order = await admin_repo.get_order_by_id(order_id)
    if order:
        order.manager_comment = new_comment
        await admin_repo.update_order(order)

    await state.clear()

    await render_order_detail(
        event=message,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
        message_id_to_edit=last_bot_msg_id,
    )