from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.repositories.shop_repo import ShopRepository
from database.repositories.user_repo import UserRepository
from handlers.client.shop.render_product import show_product_card
from handlers.client.shop.render_shop import render_shop_menu
from locales.locales import Locale
from utils.logger import logger

user_shop_router = Router()


def _parse_entity_id(data: str) -> int | None:
    """Вспомогательный безопасный парсер ID из callback_data."""
    try:
        return int(data.split("_")[-1])
    except (ValueError, IndexError):
        return None


@user_shop_router.callback_query(F.data.startswith("client_shop"))
async def shop_main(
    callback: CallbackQuery,
    shop_repo: ShopRepository,
    user_repo: UserRepository,
    state: FSMContext,
) -> None:
    """Навигация по каталогу магазина (корневое меню и категории)."""
    await state.clear()
    await callback.answer()

    data_parts = callback.data.split("_")
    current_cat_id = None

    if len(data_parts) > 2 and data_parts[2] != "root":
        try:
            current_cat_id = int(data_parts[2])
        except ValueError:
            logger.warning(f"[SHOP HANDLER] Invalid category ID format in {callback.data}")
            current_cat_id = None

    await render_shop_menu(
        event=callback,
        shop_repo=shop_repo,
        user_repo=user_repo,
        current_cat_id=current_cat_id,
        message_id_to_edit=callback.message.message_id,
    )


@user_shop_router.callback_query(F.data.startswith("prev_") | F.data.startswith("next_") | F.data.startswith("client_item_"))
async def route_product_card(
    callback: CallbackQuery,
    shop_repo: ShopRepository,
    user_repo: UserRepository,
) -> None:
    """Отображение карточки товара."""
    await callback.answer()
    product_id = _parse_entity_id(callback.data)
    if product_id is None:
        logger.warning(f"[SHOP HANDLER] Failed to parse product_id from {callback.data}")
        return

    user = await user_repo.get_user_with_cart(user_id=callback.from_user.id)
    lang = user.language if user and user.language else "ru"
    cart_count = len(user.cart) if user and user.cart else 0

    await show_product_card(
        chat_id=callback.message.chat.id,
        product_id=product_id,
        shop_repo=shop_repo,
        cart_item=cart_count,
        bot=callback.bot,
        lang=lang,
        old_message_id=callback.message.message_id,
    )


@user_shop_router.callback_query(F.data.startswith("order_"))
async def order_product(
    callback: CallbackQuery,
    user_repo: UserRepository,
    shop_repo: ShopRepository,
) -> None:
    """Добавление товара в корзину с мгновенной обратной связью и обновлением карточки."""
    product_id = _parse_entity_id(callback.data)
    if product_id is None:
        await callback.answer()
        logger.warning(f"[SHOP HANDLER] Invalid order callback payload: {callback.data}")
        return

    # Добавление товара
    await user_repo.add_to_cart(user_id=callback.from_user.id, product_id=product_id)
    user = await user_repo.get_user_with_cart(user_id=callback.from_user.id)

    lang = user.language if user and user.language else "ru"
    cart_count = len(user.cart) if user and user.cart else 0

    # Уведомление пользователю о добавлении товара в корзину
    locale = Locale(lang)
    added_msg = locale.get_text("product_added_to_cart")
    if added_msg in ("product_added_to_cart", "XXX"):
        added_msg = "🛒 Товар добавлен в корзину"

    await callback.answer(text=added_msg, show_alert=False)

    # Перерисовка карточки
    await show_product_card(
        chat_id=callback.message.chat.id,
        product_id=product_id,
        shop_repo=shop_repo,
        cart_item=cart_count,
        bot=callback.bot,
        lang=lang,
        old_message_id=callback.message.message_id,
    )