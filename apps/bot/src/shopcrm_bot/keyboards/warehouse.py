# keyboards/warehouse.py
"""Динамические клавиатуры раздела «Склад» для администратора.

Структура повторяет клиентский каталог: иерархия категорий + товары.
Callback-данные начинаются с ``admin_warehouse``, чтобы их можно было
исключить из catch-all хэндлера админ-меню.
"""
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


def _display_name(names: dict[int, str] | None, obj_id: int, fallback: str) -> str:
    """Локализованное название (fallback на имя из БД)."""
    if names and obj_id in names:
        return names[obj_id]
    return fallback


def _product_button(product, product_names: dict[int, str] | None) -> InlineKeyboardButton:
    """Кнопка товара склада: название + остаток (в наличии / заморожено).

    Архивные товары (is_active=False) помечаются 🗄.
    """
    available = (product.stock or 0) - (product.reserved or 0)
    reserved = product.reserved or 0
    icon = "🗄" if not product.is_active else "📦"
    return InlineKeyboardButton(
        text=f"{icon} {_display_name(product_names, product.id, product.name)} — {available}/{reserved}",
        callback_data=f"admin_warehouse_prod_{product.id}",
    )


def build_warehouse_root_kb(
    keyboard_factory,
    categories: list,
    products: list,
    category_names: dict[int, str] | None = None,
    product_names: dict[int, str] | None = None,
) -> InlineKeyboardMarkup:
    """Корневой экран склада: категории + товары без категории."""
    txt = keyboard_factory.get_button_text("admin.warehouse", ["back"])

    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {_display_name(category_names, category.id, category.name)}",
                callback_data=f"admin_warehouse_cat_{category.id}",
            )
        )

    for product in products:
        builder.row(_product_button(product, product_names))

    # Назад: в главное меню админа (склад — прямой ребёнок admin_main_menu)
    builder.row(
        InlineKeyboardButton(text=txt["back"], callback_data="admin_main_menu")
    )

    return builder.as_markup()


def build_warehouse_category_kb(
    keyboard_factory,
    categories: list,
    products: list,
    current_cat_id: int,
    parent_id: int | None,
    category_names: dict[int, str] | None = None,
    product_names: dict[int, str] | None = None,
) -> InlineKeyboardMarkup:
    """Экран категории склада: подкатегории + товары с остатком."""
    txt = keyboard_factory.get_button_text("admin.warehouse", ["back"])

    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {_display_name(category_names, category.id, category.name)}",
                callback_data=f"admin_warehouse_cat_{category.id}",
            )
        )

    for product in products:
        builder.row(_product_button(product, product_names))

    back_cb = f"admin_warehouse_cat_{parent_id}" if parent_id else "admin_warehouse"
    builder.row(
        InlineKeyboardButton(text=txt["back"], callback_data=back_cb)
    )

    return builder.as_markup()


def build_warehouse_product_kb(
    keyboard_factory,
    product_id: int,
    category_id: int | None,
    is_active: bool = True,
) -> InlineKeyboardMarkup:
    """Карточка товара склада: пополнение / списание / (восстановление) / удаление / назад.

    Для архивных товаров (``is_active=False``) добавляется кнопка
    «Восстановить» (возврат в каталог).
    """
    btn_keys = ["add_stock", "write_off", "delete", "back"]
    if not is_active:
        btn_keys.append("restore")
    txt = keyboard_factory.get_button_text("admin.warehouse", btn_keys)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=txt["add_stock"], callback_data=f"admin_warehouse_add_{product_id}"
        ),
        InlineKeyboardButton(
            text=txt["write_off"], callback_data=f"admin_warehouse_off_{product_id}"
        ),
    )
    if not is_active:
        builder.row(
            InlineKeyboardButton(
                text=txt["restore"],
                callback_data=f"admin_warehouse_restore_{product_id}",
            ),
        )
    builder.row(
        InlineKeyboardButton(
            text=txt["delete"], callback_data=f"admin_warehouse_del_{product_id}"
        ),
    )

    # Назад: в категорию товара (или в корень, если категории нет)
    back_cb = f"admin_warehouse_cat_{category_id}" if category_id else "admin_warehouse"
    builder.row(
        InlineKeyboardButton(text=txt["back"], callback_data=back_cb)
    )

    return builder.as_markup()


def build_warehouse_delete_confirm_kb(
    keyboard_factory,
    product_id: int,
) -> InlineKeyboardMarkup:
    """Экран подтверждения полного удаления товара."""
    txt = keyboard_factory.get_button_text(
        "admin.warehouse", ["confirm_delete", "cancel"]
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=txt["confirm_delete"],
            callback_data=f"admin_warehouse_del_confirm_{product_id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=txt["cancel"],
            callback_data=f"admin_warehouse_prod_{product_id}",
        )
    )

    return builder.as_markup()
