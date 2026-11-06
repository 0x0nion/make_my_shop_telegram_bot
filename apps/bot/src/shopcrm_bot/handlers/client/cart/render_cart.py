# handlers/client/cart/render_cart.py
import asyncio
from types import SimpleNamespace

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from shopcrm_core.db.repositories.user_repo import UserRepository

from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager


async def render_cart(
    event: CallbackQuery | Message,
    user_repo: UserRepository,
    state: FSMContext,
):
    """Рендерит текущую корзину пользователя со списком товаров, суммой и деталями доставки."""
    # Загружаем пользователя вместе с корзиной и заказами
    user = await user_repo.get_user_with_cart(user_id=event.from_user.id)

    # 1. Если пользователь не найден — показываем пустую корзину (EN по умолчанию)
    if not user:
        locale = Locale("en")
        kb_manager = locale.keyboards
        text = locale.get_text("client.cart_empty")
        main_kb = kb_manager.get_main_kb(orders=0, cart=0)
        await UIManager.show(
            event=event,
            text=text,
            reply_markup=main_kb,
        )
        return

    locale = Locale(user.language)
    kb_manager = locale.keyboards

    state_data = await state.get_data()
    cart_msg_id = state_data.get("cart_message_id")

    # 2. Если корзина пуста
    if not user.cart:
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

    # 2a. Параллельная подгрузка локализованных названий товаров (устранение N+1)
    product_names: dict[int, str] = {}
    loc_names = await asyncio.gather(
        *[
            user_repo.get_locale_text(
                entity_type="product_name",
                entity_id=item.product_id,
                lang_code=user.language,
            )
            for item in user.cart
        ]
    )
    for item, loc_name in zip(user.cart, loc_names, strict=True):
        product_names[item.product_id] = loc_name or (
            item.product.name if item.product else ""
        )

    # 2b. Блок «адрес + комментарий»: в корзине это форма заполнения,
    #     поэтому строки всегда присутствуют (с плейсхолдером, если не заполнены)
    addr_text = (
        locale.format_address(address, addr_type)
        if address
        else locale.get_text("client.cart_address_not_specified")
    )
    comm_text = comment or locale.get_text("client.cart_comment_not_specified")
    info_block = (
        f"{locale.get_text('client.order_delivery_address_label')} {addr_text}\n"
        f"{locale.get_text('client.order_comment_label')} {comm_text}\n\n"
    )

    # 2c. Единая карточка (тот же format_order, что и заказ):
    #     позиции корзины не имеют price_at_purchase — цена берется из product.price
    cart_order = SimpleNamespace(
        id=None,
        items=user.cart,
        total_price=None,
        delivery_price=0,
        delivery_address=address,
        delivery_address_type=addr_type,
        user_comment=comment,
        created_at=None,
        status=None,
    )
    text = locale.format_order(
        cart_order,
        template_key="client.cart_template",
        product_names=product_names,
        info_block=info_block,
    )

    markup = kb_manager.get_cart_kb(cart_items=user.cart, product_names=product_names)

    sent_msg = await UIManager.show(
        event=event,
        text=text,
        reply_markup=markup,
        message_id_to_edit=cart_msg_id,
    )

    if sent_msg:
        await state.update_data(cart_message_id=sent_msg.message_id)