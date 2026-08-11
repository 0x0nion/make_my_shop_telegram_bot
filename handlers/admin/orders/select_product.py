import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.order import OrderItem
from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from locales.currencies import get_currency_symbol
from src.core.ui import UIManager

logger = logging.getLogger(__name__)

order_catalog_router = Router()


# -------------------------------------------------------------------
# Вспомогательные функции отрисовки и клавиатур
# -------------------------------------------------------------------

def get_order_catalog_kb(
        kb: AdminInlineKb,
        categories: list,
        products: list,
        order_id: int,
        current_cat_id: int | None,
        parent_id: int | None,
        category_names: dict[int, str],
        status: str = "all",
        page: int = 1,
) -> InlineKeyboardMarkup:
    """
    Генератор клавиатуры каталога товаров с привязкой к конкретному order_id.
    """
    builder = InlineKeyboardBuilder()

    # 1. Категории
    for category in categories:
        cat_text = category_names.get(category.id, category.name)
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {cat_text}",
                callback_data=f"admin_order_select_cat:{order_id}:{category.id}:{status}:{page}"
            )
        )

    # 2. Товары
    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {product.name}",
                callback_data=f"admin_order_select_prod:{order_id}:{product.id}:{status}:{page}"
            )
        )

    # 3. Кнопка Назад / Назад в редактирование заказа
    back_text = kb.get_text("common.back", "⬅️ Назад")

    if current_cat_id:
        parent_target = parent_id if parent_id is not None else "root"
        builder.row(
            InlineKeyboardButton(
                text=back_text,
                callback_data=f"admin_order_select_cat:{order_id}:{parent_target}:{status}:{page}"
            )
        )
    else:
        # На самом верхнем уровне кнопка "Назад" возвращает в редактор состава заказа
        cancel_text = kb.get_text("common.cancel", "❌ Отмена")
        builder.row(
            InlineKeyboardButton(
                text=cancel_text,
                callback_data=f"admin_order_edit_items:{order_id}:{status}:{page}"
            )
        )

    return builder.as_markup()


async def render_order_catalog_ui(
        event: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        order_id: int,
        current_cat_id: int | None = None,
        status: str = "all",
        page: int = 1,
) -> None:
    """
    Функция отрисовки каталога товаров в режиме выбора товара для добавления в заказ #order_id.
    """
    admin_id = event.from_user.id
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    current_cat = None
    category_text = ""

    if current_cat_id:
        current_cat = await admin_repo.get_category_by_id(
            current_cat_id, use_temp=False, admin_id=admin_id
        )
        if current_cat:
            cat_name = (
                await admin_repo.get_locale_text(
                    entity_id=current_cat_id,
                    entity_type="category_name",
                    language_code=lang,
                    use_temp=False,
                    admin_id=admin_id,
                )
                or current_cat.name
            )

            category_text = (
                await admin_repo.get_locale_text(
                    entity_id=current_cat_id,
                    entity_type="category_description",
                    language_code=lang,
                    use_temp=False,
                    admin_id=admin_id,
                )
                or ""
            )

            shop_caption = f"📁 <b>Категория: {cat_name}</b>"
        else:
            shop_caption = "📁 <b>Категория не найдена</b>"
    else:
        shop_caption = "🏪 <b>Каталог товаров (Выбор для заказа)</b>"
        category_text = "Выберите категорию или товар для добавления в заказ."

    db_categories = await admin_repo.get_categories_by_parent(
        parent_id=current_cat_id, use_temp=False, admin_id=admin_id
    )
    db_products = await admin_repo.get_products_by_category(
        category_id=current_cat_id, use_temp=False, admin_id=admin_id
    )

    category_names: dict[int, str] = {}
    for cat in db_categories:
        loc_name = await admin_repo.get_locale_text(
            entity_id=cat.id,
            entity_type="category_name",
            language_code=lang,
            use_temp=False,
            admin_id=admin_id,
        )
        category_names[cat.id] = loc_name or cat.name

    currency = get_currency_symbol()

    body_parts = [
        f"➕ <b>Добавление товара в заказ #{order_id}</b>\n",
        shop_caption
    ]
    if category_text.strip():
        body_parts.append(category_text.strip())

    base_text = "\n".join(body_parts)

    if db_products:
        products_text = "\n".join(
            [f"• {product.name} — <b>{product.price} {currency}</b>" for product in db_products]
        )
        text = f"{base_text}\n\n<b>Товары в этой категории:</b>\n{products_text}"
    else:
        text = base_text

    parent_id = current_cat.parent_id if current_cat else None

    reply_markup = get_order_catalog_kb(
        kb=kb,
        categories=db_categories,
        products=db_products,
        order_id=order_id,
        current_cat_id=current_cat_id,
        parent_id=parent_id,
        category_names=category_names,
        status=status,
        page=page,
    )

    await UIManager.show(
        event=event,
        text=text,
        reply_markup=reply_markup,
    )


async def render_order_product_card_ui(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        order_id: int,
        product_id: int,
        status: str = "all",
        page: int = 1,
        added_msg: str | None = None,
) -> None:
    """
    Отрисовка карточки товара без медиа для максимальной скорости работы.
    """
    admin_id = callback.from_user.id
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    product = await admin_repo.get_product_by_id(
        product_id, use_temp=False, admin_id=admin_id
    )
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    prod_name = (
        await admin_repo.get_locale_text(
            entity_id=product_id,
            entity_type="product_name",
            language_code=lang,
            use_temp=False,
            admin_id=admin_id,
        )
        or product.name
    )

    prod_desc = (
        await admin_repo.get_locale_text(
            entity_id=product_id,
            entity_type="product_description",
            language_code=lang,
            use_temp=False,
            admin_id=admin_id,
        )
        or getattr(product, "description", None)
        or "Описание отсутствует."
    )

    currency = get_currency_symbol()
    cat_id = product.category_id if product.category_id is not None else "root"

    text_parts = [
        f"📦 <b>{prod_name}</b>\n",
        f"{prod_desc.strip()}\n",
        f"💵 <b>Цена:</b> {product.price} {currency}",
    ]

    if hasattr(product, "stock") and product.stock is not None:
        text_parts.append(f"📊 <b>В наличии:</b> {product.stock} шт.")

    if added_msg:
        text_parts.append(f"\n{added_msg}")

    text = "\n".join(text_parts)

    builder = InlineKeyboardBuilder()

    btn_add_text = "➕ Добавить ещё 1 шт." if added_msg else "➕ Добавить в заказ"
    builder.row(
        InlineKeyboardButton(
            text=btn_add_text,
            callback_data=f"admin_order_add_prod_exec:{order_id}:{product_id}:{status}:{page}"
        )
    )

    back_text = kb.get_text("common.back", "⬅️ Назад")
    builder.row(
        InlineKeyboardButton(
            text=back_text,
            callback_data=f"admin_order_select_cat:{order_id}:{cat_id}:{status}:{page}"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🛒 К составу заказа",
            callback_data=f"admin_order_edit_items:{order_id}:{status}:{page}"
        )
    )

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=builder.as_markup(),
    )


# -------------------------------------------------------------------
# Handlers (Роутинг)
# -------------------------------------------------------------------

@order_catalog_router.callback_query(F.data.startswith("admin_order_add_item_start:"))
async def process_add_item_start(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    await render_order_catalog_ui(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        current_cat_id=None,
        status=status,
        page=page,
    )


@order_catalog_router.callback_query(F.data.startswith("admin_order_select_cat:"))
async def process_select_category(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    cat_raw = parts[2]
    status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    cat_id = None if cat_raw == "root" else int(cat_raw)

    await render_order_catalog_ui(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        current_cat_id=cat_id,
        status=status,
        page=page,
    )


@order_catalog_router.callback_query(F.data.startswith("admin_order_select_prod:"))
async def process_select_product(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    product_id = int(parts[2])
    status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    await render_order_product_card_ui(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        product_id=product_id,
        status=status,
        page=page,
    )


@order_catalog_router.callback_query(F.data.startswith("admin_order_add_prod_exec:"))
async def process_execute_add_product(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    product_id = int(parts[2])
    status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    admin_id = callback.from_user.id

    order = await admin_repo.get_order_by_id(order_id)
    product = await admin_repo.get_product_by_id(product_id, use_temp=False, admin_id=admin_id)

    if not order or not product:
        await callback.answer("❌ Ошибка: заказ или товар не найден", show_alert=True)
        return

    # Безопасная проверка позиции с учетом возможного NULL в product_id
    existing_item = next(
        (i for i in order.items if i.product_id is not None and i.product_id == product_id),
        None
    )

    if existing_item:
        existing_item.quantity += 1
    else:
        new_item = OrderItem(
            order_id=order_id,
            product_id=product.id,
            quantity=1,
            price_at_purchase=product.price
        )
        order.items.append(new_item)

    # Безопасный расчет типов для SQLAlchemy Numeric(10, 2)
    items_sum = sum(
        int(i.quantity) * float(i.price_at_purchase)
        for i in order.items
    )
    delivery = float(order.delivery_price) if order.delivery_price is not None else 0.0

    order.total_price = items_sum + delivery

    await admin_repo.update_order(order)

    await callback.answer("✅ Товар добавлен в заказ!", show_alert=False)

    await render_order_product_card_ui(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        product_id=product_id,
        status=status,
        page=page,
        added_msg="✅ <b>Товар добавлен в заказ!</b>"
    )