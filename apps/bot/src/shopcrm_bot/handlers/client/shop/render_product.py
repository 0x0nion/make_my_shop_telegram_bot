# handlers/client/shop/render_product.py
from typing import Optional

from aiogram import Bot

from shopcrm_core.db.repositories.shop_repo import ShopRepository
from shopcrm_bot.config import config
from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager
from shopcrm_core.logging import logger


def format_product_from_template(product, locale: Locale, name: Optional[str] = None) -> str:
    """Динамический сборщик текста карточки товара с использованием локали.

    :param name: локализованное название товара (entity_type='product_name');
        при отсутствии — fallback на product.name
    """
    unit_val = locale.get_unit(getattr(product, "unit", None))
    desc_val = getattr(product, "description", None) or locale.get_text("client.no_description")

    currency_code = getattr(product, "currency", None)
    currency_val = locale.get_currency_symbol(currency_code)

    price_val = float(getattr(product, "price", 0.0) or 0.0)

    data = {
        "name": name or getattr(product, "name", ""),
        "description": desc_val,
        "price": price_val,
        "currency": currency_val,
        "unit": unit_val,
    }

    return locale.get_text("client.product_template", **data)


async def show_product_card(
    chat_id: int,
    product_id: int,
    shop_repo: ShopRepository,
    user_repo,
    bot: Bot,
    lang: str,
    cart_item: int = 0,
    old_message_id: Optional[int] = None,
):
    """Универсальная локализованная функция для отрисовки карточки товара."""
    logger.info(f"Showing product card id={product_id} for chat_id={chat_id}")
    product = await shop_repo.get_product_by_id(product_id)
    if not product:
        logger.warning(f"[SHOP UI] Product id={product_id} not found.")
        return None

    category_id = getattr(product, "category_id", None)
    current_id = getattr(product, "id", product_id)

    next_product = await shop_repo.get_next_product(
        category_id=category_id, current_product_id=current_id
    )
    prev_product = await shop_repo.get_prev_product(
        category_id=category_id, current_product_id=current_id
    )

    locale = Locale(lang)
    kb_manager = locale.keyboards

    # Локализованное название товара (entity_type='product_name') с fallback на product.name
    product_name = (
        await user_repo.get_locale_text(
            entity_type="product_name",
            entity_id=current_id,
            lang_code=lang,
        )
        or product.name
    )

    text = format_product_from_template(product=product, locale=locale, name=product_name)
    manager_url = config.MANAGER_URL or None

    reply_markup = kb_manager.get_product_card_kb(
        product_id=current_id,
        category_id=category_id,
        prev_id=getattr(prev_product, "id", None) if prev_product else None,
        next_id=getattr(next_product, "id", None) if next_product else None,
        cart_item=cart_item,
        manager_url=manager_url,
    )

    # Передаем напрямую bot и chat_id — без создания фейковых Message
    return await UIManager.show(
        bot=bot,
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        photo=getattr(product, "image_id", None),
        message_id_to_edit=old_message_id,
    )