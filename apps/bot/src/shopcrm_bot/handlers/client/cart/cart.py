# handlers/client/cart/cart.py
import logging
from contextlib import suppress
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from shopcrm_core.db.models import User
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_bot.handlers.client.cart.render_cart import render_cart
from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager
from shopcrm_core.services.address_service import build_location_address, normalize_text_address
from shopcrm_bot.states.user_states import UserState

logger = logging.getLogger(__name__)

user_cart_router = Router()


@user_cart_router.callback_query(F.data == "client_cart")
async def shop_main(
    callback: CallbackQuery,
    user_repo: UserRepository,
    state: FSMContext,
):
    await state.set_state(None)
    await state.update_data(cart_message_id=callback.message.message_id)
    await render_cart(event=callback, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data == "set_address")
async def get_address(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
):
    locale = Locale(user.language)
    kb = locale.keyboards

    await state.set_state(UserState.waiting_for_address)
    await state.update_data(cart_message_id=callback.message.message_id)

    await UIManager.show(
        event=callback,
        text=locale.get_text("client.user_set_address"),
        reply_markup=kb.get_back_kb("cancel_input"),
    )


@user_cart_router.message(UserState.waiting_for_address)
async def process_address(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    user: User,
):
    locale = Locale(user.language)
    kb = locale.keyboards

    with suppress(TelegramBadRequest):
        await message.delete()

    address = None
    addr_type = None

    if message.location:
        address, addr_type = build_location_address(
            message.location.latitude, message.location.longitude
        )
    elif message.text:
        address, addr_type = normalize_text_address(message.text)

    if address:
        await state.update_data(delivery_address=address, delivery_address_type=addr_type)
        await state.set_state(None)
        await render_cart(event=message, user_repo=user_repo, state=state)
    else:
        data = await state.get_data()
        cart_msg_id = data.get("cart_message_id")
        await UIManager.show(
            event=message,
            text=f"{locale.get_text('client.user_set_address')}\n\n{locale.get_text('client.user_set_address_error')}",
            reply_markup=kb.get_back_kb("cancel_input"),
            message_id_to_edit=cart_msg_id,
        )


@user_cart_router.callback_query(F.data == "set_comment")
async def ask_comment(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
):
    locale = Locale(user.language)
    kb = locale.keyboards

    await state.set_state(UserState.waiting_for_comment)
    await state.update_data(cart_message_id=callback.message.message_id)

    await UIManager.show(
        event=callback,
        text=locale.get_text("client.user_set_comment"),
        reply_markup=kb.get_back_kb("cancel_input"),
    )


@user_cart_router.message(UserState.waiting_for_comment)
async def process_comment(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    user: User,
):
    with suppress(TelegramBadRequest):
        await message.delete()

    if message.text:
        await state.update_data(user_comment=message.text.strip())
        await state.set_state(None)
        await render_cart(event=message, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data == "cancel_input")
async def cancel_input(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
):
    await state.set_state(None)
    await render_cart(event=callback, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data.startswith(("inc_", "dec_")))
async def update_quantity(
    callback: CallbackQuery,
    user_repo: UserRepository,
    state: FSMContext,
):
    try:
        action, product_id_str = callback.data.split("_")
        product_id = int(product_id_str)
    except (ValueError, IndexError):
        logger.warning(f"[CART HANDLER] Invalid quantity callback: {callback.data}")
        await callback.answer()
        return

    change = 1 if action == "inc" else -1

    await user_repo.update_cart_item(
        user_id=callback.from_user.id,
        product_id=product_id,
        change=change,
    )
    await render_cart(event=callback, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data == "checkout_confirm")
async def checkout_order(
        callback: CallbackQuery,
        user_repo: UserRepository,
        state: FSMContext,
        user: User,
):
    locale = Locale(user.language)
    kb = locale.keyboards

    user_data = await state.get_data()
    delivery_address = user_data.get("delivery_address")
    delivery_address_type = user_data.get("delivery_address_type")
    user_comment = user_data.get("user_comment")

    order = await user_repo.create_order_from_cart(
        user_id=user.id,
        delivery_address=delivery_address,
        delivery_address_type=delivery_address_type,
        user_comment=user_comment,
    )

    if not order:
        await callback.answer(
            text=locale.get_text("client.user_empty_cart"), show_alert=True
        )
        await render_cart(event=callback, user_repo=user_repo, state=state)
        return

    await state.clear()

    success_text = locale.format_order(order)

    updated_user = await user_repo.get_user_with_cart(user_id=callback.from_user.id)

    orders_count = updated_user.active_orders_count if updated_user else 0
    cart_count = len(updated_user.cart) if updated_user else 0

    await UIManager.show(
        event=callback,
        text=success_text,
        reply_markup=kb.get_main_kb(
            orders=orders_count,
            cart=cart_count,
        ),
    )