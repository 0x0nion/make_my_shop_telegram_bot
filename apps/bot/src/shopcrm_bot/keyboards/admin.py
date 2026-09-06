import logging
from typing import Dict, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


def build_catalog_edit_kb(
    keyboard_factory,
    categories: list,
    products: list,
    current_cat_id: Optional[int | None],
    parent_id: Optional[int],
    category_names: Optional[Dict[int, str]] = None,
    has_description: bool = False,
) -> InlineKeyboardMarkup:
    """Динамический конструктор управления категориями и товарами магазина."""
    kb_path = "admin.catalog_navigation"

    # Забираем ВСЕ тексты за один вызов
    txt = keyboard_factory.get_button_text(
        kb_path,
        [
            "back",
            "to_main_menu",
            "delete",
            "add_subcategory",
            "add_product",
            "add_tittle",
            "delete_tittle",
            "save_changes",
        ],
    )

    builder = InlineKeyboardBuilder()
    cat_suffix = f"_{current_cat_id}" if current_cat_id else "_root"

    # 1. Навигация "Назад" / "В главное меню"
    if current_cat_id:
        parent_to_go = parent_id if parent_id else "root"
        builder.row(
            InlineKeyboardButton(
                text=txt["back"], callback_data=f"admin_catalog_{parent_to_go}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=txt["to_main_menu"], callback_data="admin_shop_settings"
            )
        )

    # 2. Список подкатегорий
    for category in categories:
        cat_display_name = (
            category_names.get(category.id)
            if category_names and category.id in category_names
            else category.name
        )
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {cat_display_name}",
                callback_data=f"admin_catalog_{category.id}",
            ),
            InlineKeyboardButton(
                text=txt["delete"],
                callback_data=f"admin_edit_cat:del_cat_{category.id}",
            ),
        )

    # 3. Список товаров
    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {product.name}",
                callback_data=f"admin_item_{product.id}",
            ),
            InlineKeyboardButton(
                text=txt["delete"],
                callback_data=f"admin_edit_cat:del_item_{product.id}",
            ),
        )

    # 4. Управление и добавление
    builder.row(
        InlineKeyboardButton(
            text=txt["add_subcategory"],
            callback_data=f"admin_edit_cat:add_cat{cat_suffix}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=txt["add_product"],
            callback_data=f"admin_edit_cat:add_item{cat_suffix}",
        )
    )

    # 5. Кнопки описания
    title_row = [
        InlineKeyboardButton(
            text=txt["add_tittle"],
            callback_data=f"admin_edit_cat:add_tittle{cat_suffix}",
        )
    ]
    if has_description:
        title_row.append(
            InlineKeyboardButton(
                text=txt["delete_tittle"],
                callback_data=f"admin_edit_cat:del_tittle{cat_suffix}",
            )
        )
    builder.row(*title_row)

    # 6. Сохранение
    builder.row(
        InlineKeyboardButton(
            text=txt["save_changes"], callback_data="admin_edit_cat:save_shop"
        )
    )

    return builder.as_markup()