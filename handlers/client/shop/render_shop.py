# handlers/client/shop/render_shop.py
import asyncio
from aiogram.types import CallbackQuery, Message

from database.repositories.shop_repo import ShopRepository
from database.repositories.user_repo import UserRepository
from locales.locale import Locale
from src.core.ui import UIManager
from src.ui.presenters.catalog import build_catalog_text
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
    kb_manager = locale.keyboards

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
                "catalog.display.category_title", name=cat_name
            )
        else:
            logger.warning(f"[SHOP] Category id={current_cat_id} not found.")
            shop_caption = locale.get_text("catalog.display.category_not_found")
    else:
        # Корневое меню магазина (entity_id = 0)
        shop_caption = locale.get_text("catalog.display.root_title")
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

    # 4. Формирование итогового текста сообщения (единый формат с админом)
    text = build_catalog_text(
        locale=locale,
        title=shop_caption,
        description=category_text,
        products=db_products,
    )

    # 5. Сборка клавиатуры через единый KeyboardFactory
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