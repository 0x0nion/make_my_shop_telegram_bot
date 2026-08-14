from typing import Union
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.repositories.user_repo import UserRepository
from keyboards.inline import InlineKb
from locales.currencies import DEFAULT_CURRENCY
from locales.locales import Locale
from src.core.ui import UIManager


async def render_cart(
        event: Union[CallbackQuery, Message],
        user_repo: UserRepository,
        state: FSMContext,
):
    """Рендерит текущую корзину пользователя со списком товаров, суммой и деталями доставки."""
    # Загружаем пользователя вместе с корзиной и заказами
    user = await user_repo.get_user_with_cart(user_id=event.from_user.id)
    lang = user.language if user and user.language else "ru"

    locale = Locale(lang)
    kb_manager = InlineKb(lang)

    state_data = await state.get_data()
    cart_msg_id = state_data.get("cart_message_id")

    # 1. Если корзина пуста
    if not user or not user.cart:
        text = locale.get_text("cart_empty")
        if text in ("cart_empty", "XXX"):
            text = "🛒 Ваша корзина пуста."

        orders_list = getattr(user, "orders", []) or []
        main_kb = kb_manager.get_main_kb(orders=len(orders_list), cart=0)

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
    comment = state_data.get("user_comment", "")

    subtotal = 0.0
    text_blocks = []

    # Заголовок
    cart_title = locale.get_text("cart_title")
    if cart_title in ("cart_title", "XXX"):
        cart_title = "<b>🛒 Ваша корзина:</b>\n"
    text_blocks.append(cart_title)

    # Позиции
    for item in user.cart:
        if not item.product:
            continue

        price = float(getattr(item.product, "price", 0.0) or 0.0)
        quantity = int(getattr(item, "quantity", 1) or 1)
        item_total = price * quantity
        subtotal += item_total

        product_name = getattr(item.product, "name", "Товар")
        unit_raw = getattr(item.product, "unit", None)
        unit_val = locale.get_unit(unit_raw) if hasattr(locale, "get_unit") else (unit_raw or "шт")

        # TODO: заготовка под разные валюты
        currency = locale.get_currency_symbol(DEFAULT_CURRENCY)

        # Передаем расширенный набор аргументов, чтобы локаль не падала при любых ключах в шаблоне
        line = locale.get_text(
            "cart_item_line",
            name=product_name,
            quantity=quantity,
            price=price,
            item_total=item_total,
            unit=unit_val,
            currency=currency
        )

        # Фолбэк, если ключа нет в локали
        if line in ("cart_item_line", "XXX"):
            line = f"• <b>{product_name}</b> — {quantity} {unit_val} x {price:.2f} = <b>{item_total:.2f}</b>"

        text_blocks.append(line)

    # Итоговая сумма
    summary_text = locale.get_text("cart_summary_subtotal", subtotal=float(subtotal), currency=currency)
    if summary_text in ("cart_summary_subtotal", "XXX"):
        summary_text = f"\n<b>Итого: {subtotal:.2f}</b>"
    text_blocks.append(summary_text)

    # Адрес
    addr_text = address if address else locale.get_text("cart_address_not_specified")
    if addr_text in ("cart_address_not_specified", "XXX"):
        addr_text = "Не указан"

    addr_label = locale.get_text("cart_address_label", address=addr_text)
    if addr_label in ("cart_address_label", "XXX"):
        addr_label = f"📍 <b>Адрес:</b> {addr_text}"
    text_blocks.append(addr_label)

    # Комментарий
    comm_text = comment if comment else locale.get_text("cart_comment_not_specified")
    if comm_text in ("cart_comment_not_specified", "XXX"):
        comm_text = "Нет"

    comm_label = locale.get_text("cart_comment_label", comment=comm_text)
    if comm_label in ("cart_comment_label", "XXX"):
        comm_label = f"💬 <b>Комментарий:</b> {comm_text}"
    text_blocks.append(comm_label)

    # Формируем итоговый текст с правильными переносами
    text = "\n".join(text_blocks)

    markup = kb_manager.get_cart_kb(
        cart_items=user.cart,
        has_address=bool(address),
    )

    sent_msg = await UIManager.show(
        event=event,
        text=text,
        reply_markup=markup,
        message_id_to_edit=cart_msg_id,
    )

    if sent_msg:
        await state.update_data(cart_message_id=sent_msg.message_id)