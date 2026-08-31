from typing import Dict, Optional, Tuple, Any
from aiogram.types import InlineKeyboardMarkup


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
                title = locale.get_text("catalog.category_title", name=cat_name)
                description = category_description or ""
            else:
                title = locale.get_text("catalog.category_not_found")
                description = ""
        else:
            title = locale.get_text("catalog.root_menu_title")
            description = (
                root_description
                if root_description and root_description.strip()
                else locale.get_text("catalog.root_menu_description")
            )

        has_description = bool(description and description.strip())

        # 2. Собираем основной текст
        body = [title.strip()]
        if has_description:
            body.append(description.strip())

        base_text = "\n\n".join(body)

        # 3. Добавляем список товаров, если они есть
        if db_products:
            currency = locale.get_currency_symbol()
            products_text = "\n".join(
                f"{p.name} - {p.price} {currency}" for p in db_products
            )
            full_text = f"{base_text}\n{'_' * 20}\n{products_text}"
        else:
            full_text = base_text

        # 4. Собираем клавиатуру
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