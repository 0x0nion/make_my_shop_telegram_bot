from contextlib import suppress
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.models import User
from database.repositories.user_repo import UserRepository
from handlers.client.cart.render_cart import render_cart
from keyboards.inline import InlineKb
from locales.locales import Locale
from src.core.ui import UIManager
from state.user_states import UserState

user_cart_router = Router()


@user_cart_router.callback_query(F.data == "client_cart")
async def shop_main(callback: CallbackQuery, user_repo: UserRepository, state: FSMContext):
    await state.set_state(None)
    await state.update_data(cart_message_id=callback.message.message_id)
    await render_cart(event=callback, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data == "set_address")
async def get_address(callback: CallbackQuery, state: FSMContext, user_repo: UserRepository):
    await state.set_state(UserState.waiting_for_address)
    user = await user_repo.get_user(callback.from_user.id)
    await state.update_data(cart_message_id=callback.message.message_id)

    await UIManager.show(
        event=callback,
        text=Locale(user.language).get_text('user_set_address'),
        reply_markup=InlineKb(user.language).get_kb('cancel')
    )


@user_cart_router.message(UserState.waiting_for_address)
async def process_address(message: Message, state: FSMContext, user_repo: UserRepository):
    with suppress(TelegramBadRequest):
        await message.delete()

    user = await user_repo.get_user(message.from_user.id)

    address = None
    if message.location:
        latitude = message.location.latitude
        longitude = message.location.longitude
        maps_url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
        address = Locale(user.language).format_address(maps_url)
    elif message.text:
        address = message.text.strip()

    if address:
        await state.update_data(delivery_address=address)
        await state.set_state(None)
        await render_cart(event=message, user_repo=user_repo, state=state)
    else:
        # Уведомляем пользователя о некорректном вводе, не ломая интерфейс
        await message.answer(text=Locale(user.language).get_text('user_set_address_error'))


@user_cart_router.callback_query(F.data == "set_comment")
async def ask_comment(callback: CallbackQuery, user_repo: UserRepository, state: FSMContext):
    await state.set_state(UserState.waiting_for_comment)
    user = await user_repo.get_user(callback.from_user.id)
    await state.update_data(cart_message_id=callback.message.message_id)

    await UIManager.show(
        event=callback,
        text=Locale(user.language).get_text('user_set_comment'),
        reply_markup=InlineKb(user.language).get_kb('cancel')
    )


@user_cart_router.message(UserState.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext, user_repo: UserRepository):
    with suppress(TelegramBadRequest):
        await message.delete()

    if message.text:
        await state.update_data(user_comment=message.text.strip())
        await state.set_state(None)
        await render_cart(event=message, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data == "cancel_input")
async def cancel_input(callback: CallbackQuery, state: FSMContext, user_repo: UserRepository):
    await state.set_state(None)
    await render_cart(event=callback, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data.startswith(("inc_", "dec_")))
async def update_quantity(callback: CallbackQuery, user_repo: UserRepository, state: FSMContext):
    action, product_id = callback.data.split("_")
    change = 1 if action == "inc" else -1

    await user_repo.update_cart_item(
        user_id=callback.from_user.id,
        product_id=int(product_id),
        change=change
    )
    await render_cart(event=callback, user_repo=user_repo, state=state)


@user_cart_router.callback_query(F.data == "checkout_confirm")
async def checkout_order(callback: CallbackQuery, user_repo: UserRepository, state: FSMContext):
    user_id = callback.from_user.id
    user = await user_repo.get_user_with_cart(user_id=user_id)
    locale = Locale(user.language)

    user_data = await state.get_data()
    delivery_address = user_data.get("delivery_address")
    user_comment = user_data.get("user_comment")

    order = await user_repo.create_order_from_cart(
        user_id=user_id,
        delivery_address=delivery_address,
        user_comment=user_comment
    )

    if not order:
        await callback.answer(text=locale.get_text('user_empty_cart'), show_alert=True)
        await render_cart(event=callback, user_repo=user_repo, state=state)
        return

    await state.clear()

    success_text = locale.format_order(order)
    updated_user = await user_repo.get_user_with_cart(user_id=user_id)

    await UIManager.show(
        event=callback,
        text=success_text,
        reply_markup=InlineKb(user.language).get_main_kb(
            orders=len(updated_user.orders) if hasattr(updated_user, "orders") else 0,
            cart=len(updated_user.cart) if hasattr(updated_user, "cart") else 0
        )
    )
