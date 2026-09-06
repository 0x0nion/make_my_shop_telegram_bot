# handlers/client/cart/render_cart.py
from typing import Union

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.repositories.user_repo import UserRepository
from locales.currencies import DEFAULT_CURRENCY
from locales.locale import Locale
from src.core.ui import UIManager


async def render_cart(
    event: Union[CallbackQuery, Message],
    user_repo: UserRepository,
    state: FSMContext,
):
    """Рендерит текущую корзину пользователя со списком товаров, суммой и деталями доставки."""
    # Загружаем пользователя вместе с корзиной и заказами
    user = await user_repo.get_user_with_cart(user_id=event.from_user.id)

    locale = Locale(user.language)
    kb_manager = locale.keyboards

    state_data = await state.get_data()
    cart_msg_id = state_data.get("cart_message_id")

    # 1. Если корзина пуста
    if not user or not user.cart:
        text = locale.get_text("client.cart_empty")
        main_kb = kb_manager.get_main_kb(orders=user.active_orders_count, cart=0)

        sent_msg = await UIManager.show(
            event=event,
            text=text,
            reply_markup=main_kb,
            message_id_to_edit=cart_msg_id,
        )
        if sent_msg:
            await state.update_data(cart_message_id=sent_msg.message_id)
        return

    # 2. Расчет содержимого корзины
    address = state_data.get("delivery_address")
    addr_type = state_data.get("delivery_address_type")
    comment = state_data.get("user_comment", "")

    subtotal = 0.0
    text_blocks = []

    # Заголовок
    text_blocks.append(locale.get_text("client.cart_title"))

    # Символ валюты
    currency = locale.get_currency_symbol(DEFAULT_CURRENCY)

    # Позиции
    for item in user.cart:
        if not item.product:
            continue

        price = float(getattr(item.product, "price", 0.0) or 0.0)
        quantity = int(getattr(item, "quantity", 1) or 1)
        item_total = price * quantity
        subtotal += item_total

        product_name = getattr(item.product, "name", "")
        unit_raw = getattr(item.product, "unit", None)
        unit_val = locale.get_unit(unit_raw)

        line = locale.get_text(
            "client.cart_item_line",
            name=product_name,
            quantity=quantity,
            price=f"{price:.2f}",
            item_total=f"{item_total:.2f}",
            unit=unit_val,
            currency=currency,
        )
        text_blocks.append(line)

    # Итоговая сумма
    summary_text = locale.get_text(
        "client.cart_summary_subtotal",
        subtotal=f"{subtotal:.2f}",
        currency=currency,
    )
    text_blocks.append(summary_text)

    # Адрес
    addr_text = locale.format_address(address, addr_type) if address else locale.get_text("client.cart_address_not_specified")
    addr_label = locale.get_text("client.cart_address_label", address=addr_text)
    text_blocks.append(addr_label)

    # Комментарий
    comm_text = comment if comment else locale.get_text("client.cart_comment_not_specified")
    comm_label = locale.get_text("client.cart_comment_label", comment=comm_text)
    text_blocks.append(comm_label)

    # Формируем итоговый текст с правильными переносами
    text = "\n".join(text_blocks)

    markup = kb_manager.get_cart_kb(cart_items=user.cart)

    sent_msg = await UIManager.show(
        event=event,
        text=text,
        reply_markup=markup,
        message_id_to_edit=cart_msg_id,
    )

    if sent_msg:
        await state.update_data(cart_message_id=sent_msg.message_id)