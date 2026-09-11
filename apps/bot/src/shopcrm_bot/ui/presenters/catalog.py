from typing import Dict, Optional, Tuple, Any
from aiogram.types import InlineKeyboardMarkup

# Единый разделитель списка товаров в каталоге (клиент и админ).
_CATALOG_SEPARATOR = "─" * 15


def build_catalog_text(
        locale,
        title: str,
        description: str,
        products: list,
) -> str:
    """Единый формат текста каталога для клиента и админа.

    Формат:
        {title}

        {description}

        ───────────────

        🔹 {name} - {price} {currency} / шт.

        ───────────────
        ℹ️ {footer}

    Список товаров (и футер) добавляется только если товары есть.
    """
    parts = [title.strip()]
    if description and description.strip():
        parts.append(description.strip())
    base_text = "\n\n".join(parts)

    if not products:
        return base_text

    lines = []
    for product in products:
        price = float(getattr(product, "price", 0.0) or 0.0)
        currency = locale.get_currency_symbol(getattr(product, "currency", None))
        line = locale.get_text(
            "catalog.display.product_line",
            name=getattr(product, "name", ""),
            price=f"{price:,.2f}",
            currency=currency,
        )
        lines.append(line)

    products_text = "\n\n".join(lines)
    footer = locale.get_text("catalog.display.footer")
    return (
        f"{base_text}\n\n{_CATALOG_SEPARATOR}\n\n"
        f"{products_text}\n\n{_CATALOG_SEPARATOR}\n{footer}"
    )


class CatalogMenuPresenter:
    """Отвечает за сборку финального текста и клавиатуры экрана каталога."""

    @staticmethod
    def render(
            locale,
            current_cat: Optional[Any],
            current_cat_id: Optional[int],
            db_categories: list,
            db_products: list,
            category_names: Dict[int, str],
            category_description: Optional[str],
            root_description: Optional[str],
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Формирует готовый текст экрана и клавиатуру."""

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
        )

        return full_text, reply_markup