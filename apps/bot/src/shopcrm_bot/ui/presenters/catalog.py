from typing import Any

from aiogram.types import InlineKeyboardMarkup
from shopcrm_core.utils import format_price


def build_catalog_text(
        locale,
        title: str,
        description: str,
        products: list,
        product_names: dict[int, str] | None = None,
) -> str:
    """Единый формат текста каталога для клиента и админа.

    Формат (компактный список, как «Состав заказа», без разделительных линий):
        {title}

        {description}

        🛒 <b>Товары:</b>
        1. <b>{name}</b> — {price} {currency} / {unit}
        2. <b>{name}</b> — {price} {currency} / {unit}

        ℹ️ {footer}

    Описание категории показывается только если оно заполнено.
    Список товаров (и футер) добавляется только если товары есть.

    :param product_names: словарь product_id -> локализованное название
        (entity_type='product_name'); при отсутствии — fallback на product.name
    """
    parts = [title.strip()]
    if description and description.strip():
        parts.append(description.strip())
    base_text = "\n\n".join(parts)

    if not products:
        return base_text

    lines = []
    for idx, product in enumerate(products, start=1):
        currency = locale.get_currency_symbol(getattr(product, "currency", None))
        unit_val = locale.get_unit(getattr(product, "unit", None))
        line = locale.get_text(
            "catalog.display.product_line",
            idx=idx,
            name=(product_names or {}).get(product.id) or getattr(product, "name", ""),
            price=format_price(getattr(product, "price", 0) or 0),
            currency=currency,
            unit=unit_val,
        )
        lines.append(line)

    products_header = locale.get_text("catalog.display.products_header")
    footer = locale.get_text("catalog.display.footer")
    return f"{base_text}\n\n{products_header}\n" + "\n".join(lines) + f"\n\n{footer}"


class CatalogMenuPresenter:
    """Отвечает за сборку финального текста и клавиатуры экрана каталога."""

    @staticmethod
    def render(
            locale,
            current_cat: Any | None,
            current_cat_id: int | None,
            db_categories: list,
            db_products: list,
            category_names: dict[int, str],
            category_description: str | None,
            root_description: str | None,
            product_names: dict[int, str] | None = None,
    ) -> tuple[str, InlineKeyboardMarkup]:
        """Формирует готовый текст экрана и клавиатуру.

        :param product_names: словарь product_id -> локализованное название
            (entity_type='product_name'); при отсутствии — fallback на product.name
        """

        # 1. Определяем заголовок и описание
        if current_cat_id:
            if current_cat:
                cat_name = category_names.get(current_cat_id, current_cat.name)
                title = locale.get_text("catalog.display.category_title", name=cat_name)
                description = category_description or ""
            else:
                title = locale.get_text("catalog.display.category_not_found")
                description = ""
        else:
            title = locale.get_text("catalog.display.root_title")
            description = root_description or ""

        has_description = bool(description and description.strip())

        # 2. Единый текст каталога (общий с клиентом)
        full_text = build_catalog_text(
            locale=locale,
            title=title,
            description=description,
            products=db_products,
            product_names=product_names,
        )

        # 3. Собираем клавиатуру
        parent_id = current_cat.parent_id if current_cat else None
        reply_markup = locale.keyboards.build_catalog_edit_kb(
            categories=db_categories,
            products=db_products,
            current_cat_id=current_cat_id,
            parent_id=parent_id,
            category_names=category_names,
            has_description=has_description,
            product_names=product_names,
        )

        return full_text, reply_markup