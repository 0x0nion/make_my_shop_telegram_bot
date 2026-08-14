import asyncio
from aiogram.types import CallbackQuery, Message

from database.repositories.shop_repo import ShopRepository
from database.repositories.user_repo import UserRepository
from keyboards.client_inline import ClientInlineKb
from locales.locales import Locale
from src.core.ui import UIManager
from utils.logger import logger


async def render_shop_menu(
    event: CallbackQuery | Message,
    shop_repo: ShopRepository,
    user_repo: UserRepository,
    current_cat_id: int | None = None,
    message_id_to_edit: int | None = None,
) -> None:
    """Универсальная и безопасная функция отрисовки интерфейса магазина для клиента."""
    user_id = event.from_user.id
    user = await user_repo.get_user(user_id=user_id)

    locale = Locale(user.language)
    kb_manager = ClientInlineKb(lang=user.language)

    current_cat = None
    parent_id = None
    category_text = ""

    # 1. Загрузка данных текущей категории и ее локализаций из БД
    if current_cat_id:
        current_cat = await shop_repo.get_category_by_id(current_cat_id)
        if current_cat:
            parent_id = current_cat.parent_id

            # Локализованное название категории
            cat_name = (
                await user_repo.get_locale_text(
                    entity_type="category_name",
                    entity_id=current_cat_id,
                    lang_code=user.language,
                )
                or current_cat.name
            )

            # Локализованное описание категории
            category_text = (
                await user_repo.get_locale_text(
                    entity_type="category_description",
                    entity_id=current_cat_id,
                    lang_code=user.language,
                )
                or ""
            )

            shop_caption = locale.get_text(
                "shop_category_title", cat_name=cat_name
            )
        else:
            logger.warning(f"[SHOP] Category id={current_cat_id} not found.")
            shop_caption = locale.get_text("shop_category_not_found")
    else:
        # Корневое меню магазина (entity_id = 0)
        shop_caption = locale.get_text("shop_main_menu_title")
        category_text = (
            await user_repo.get_locale_text(
                entity_type="category_description",
                entity_id=0,
                lang_code=user.language,
            )
            or ""
        )

    # 2. Параллельное получение дочерних категорий и товаров
    db_categories, db_products = await asyncio.gather(
        shop_repo.get_categories_by_parent(parent_id=current_cat_id),
        shop_repo.get_products_by_category(category_id=current_cat_id),
    )

    # 3. Параллельная подгрузка локализованных имен для кнопок подкатегорий (устранение N+1)
    category_names: dict[int, str] = {}
    if db_categories:
        loc_names = await asyncio.gather(
            *[
                user_repo.get_locale_text(
                    entity_type="category_name",
                    entity_id=cat.id,
                    lang_code=user.language,
                )
                for cat in db_categories
            ]
        )
        for cat, loc_name in zip(db_categories, loc_names):
            category_names[cat.id] = loc_name or cat.name

    # 4. Формирование итогового текста сообщения
    body_parts = [shop_caption.strip()]
    if category_text.strip():
        body_parts.append(category_text.strip())

    base_text = "\n\n".join(body_parts)

    if db_products:
        products_lines = []
        for product in db_products:
            raw_price = (
                float(product.price) if product.price is not None else 0.0
            )

            # Символ валюты берем из объекта товара или используем фоллбэк дефолтной валюты
            prod_currency_code = getattr(product, "currency", None)
            currency_sym = locale.get_currency_symbol(prod_currency_code)

            # Безопасное форматирование через SafeDict в get_text
            line = locale.get_text(
                "shop_product_line",
                id=product.id,
                name=product.name,
                price=f"{raw_price:.2f}",
                currency=currency_sym,
            )

            products_lines.append(line)

        products_text = "\n".join(products_lines)
        text = f"{base_text}\n{'_' * 20}\n{products_text}"
    else:
        text = base_text

    # 5. Сборка клавиатуры через ClientInlineKb
    reply_markup = kb_manager.get_shop_keyboard(
        categories=db_categories,
        products=db_products,
        current_cat_id=current_cat_id,
        parent_id=parent_id,
        category_names=category_names,
    )

    # 6. Безопасный рендеринг через UIManager
    await UIManager.show(
        event=event,
        text=text,
        reply_markup=reply_markup,
        message_id_to_edit=message_id_to_edit,
    )