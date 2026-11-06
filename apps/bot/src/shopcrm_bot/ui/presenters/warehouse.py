# ui/presenters/warehouse.py
"""Пресентер раздела «Склад»: сборка текста и клавиатуры экранов.

Работает только с реальными товарами (не черновиками каталога).
Структура навигации повторяет клиентский каталог: иерархия категорий + товары.
"""
import asyncio

from aiogram.types import CallbackQuery, Message
from shopcrm_core.db.models import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository

from shopcrm_bot.keyboards.warehouse import (
    build_warehouse_category_kb,
    build_warehouse_product_kb,
    build_warehouse_root_kb,
)
from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager


class WarehouseUI:
    """Сборка текста и клавиатуры экранов склада."""

    @staticmethod
    async def show_root(
        event: Message | CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        locale: Locale,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Корневой экран склада: дашборд всех товаров по категориям.

        Показывает все товары, сгруппированные по категориям, с остатком
        (в наличии / заморожено). Если список не помещается в сообщение —
        обрезаем и добавляем «… и ещё N товаров».
        """
        db_categories = await admin_repo.get_categories_by_parent(parent_id=None)
        db_products = await admin_repo.get_all_products()
        db_no_cat_products = [p for p in db_products if p.category_id is None]

        category_names, product_names = await WarehouseUI._load_names(
            admin_repo, user, db_categories, db_products
        )

        title = locale.get_text("admin.warehouse.root_title")
        text = WarehouseUI._build_dashboard_text(
            locale, title, db_categories, db_products, category_names, product_names
        )

        reply_markup = build_warehouse_root_kb(
            locale.keyboards,
            categories=db_categories,
            products=db_no_cat_products,
            category_names=category_names,
            product_names=product_names,
        )

        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def show_category(
        event: Message | CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        locale: Locale,
        category_id: int,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Экран категории склада: подкатегории + товары с остатком."""
        current_cat = await admin_repo.get_category_by_id(category_id=category_id)
        if not current_cat:
            await WarehouseUI.show_root(
                event=event,
                admin_repo=admin_repo,
                user=user,
                locale=locale,
                message_id_to_edit=message_id_to_edit,
            )
            return

        parent_id = current_cat.parent_id
        db_categories = await admin_repo.get_categories_by_parent(parent_id=category_id)
        db_products = await admin_repo.get_products_by_category(category_id=category_id)

        category_names, product_names = await WarehouseUI._load_names(
            admin_repo, user, db_categories, db_products
        )
        cat_name = await admin_repo.get_locale_text(
            entity_id=current_cat.id,
            entity_type="category_name",
            language_code=user.language,
        )
        category_names[current_cat.id] = cat_name or current_cat.name

        title = locale.get_text(
            "admin.warehouse.category_title",
            name=category_names.get(category_id, current_cat.name),
        )
        text = WarehouseUI._build_list_text(locale, title, db_products, product_names)

        reply_markup = build_warehouse_category_kb(
            locale.keyboards,
            categories=db_categories,
            products=db_products,
            current_cat_id=category_id,
            parent_id=parent_id,
            category_names=category_names,
            product_names=product_names,
        )

        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def show_product(
        event: Message | CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        locale: Locale,
        product_id: int,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Карточка товара склада: остаток + кнопки пополнения/списания."""
        product = await admin_repo.get_product_by_id(product_id)
        if not product:
            await WarehouseUI.show_root(
                event=event,
                admin_repo=admin_repo,
                user=user,
                locale=locale,
                message_id_to_edit=message_id_to_edit,
            )
            return

        prod_name = await admin_repo.get_locale_text(
            entity_id=product.id,
            entity_type="product_name",
            language_code=user.language,
        )
        display_name = prod_name or product.name
        available = (product.stock or 0) - (product.reserved or 0)
        reserved = product.reserved or 0

        text = locale.get_text(
            "admin.warehouse.product_title",
            name=display_name,
            available=available,
            reserved=reserved,
            unit=locale.get_unit(product.unit),
        )

        reply_markup = build_warehouse_product_kb(
            locale.keyboards,
            product_id=product_id,
            category_id=product.category_id,
        )

        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def _load_names(
        admin_repo: AdminRepository,
        user: User,
        categories: list,
        products: list,
    ) -> tuple[dict[int, str], dict[int, str]]:
        """Параллельная подгрузка локализованных названий категорий и товаров."""
        cat_tasks = [
            admin_repo.get_locale_text(
                entity_id=cat.id,
                entity_type="category_name",
                language_code=user.language,
            )
            for cat in categories
        ]
        prod_tasks = [
            admin_repo.get_locale_text(
                entity_id=p.id,
                entity_type="product_name",
                language_code=user.language,
            )
            for p in products
        ]

        results = await asyncio.gather(*cat_tasks, *prod_tasks)
        cat_results = results[: len(categories)]
        prod_results = results[len(categories):]

        category_names: dict[int, str] = {}
        for cat, loc_name in zip(categories, cat_results, strict=True):
            category_names[cat.id] = loc_name or cat.name

        product_names: dict[int, str] = {}
        for p, loc_name in zip(products, prod_results, strict=True):
            product_names[p.id] = loc_name or p.name

        return category_names, product_names

    @staticmethod
    def _build_list_text(
        locale: Locale,
        title: str,
        products: list,
        product_names: dict[int, str],
    ) -> str:
        """Текст экрана категории: заголовок + список товаров (в наличии / заморожено)."""
        if not products:
            return title

        lines = []
        for idx, product in enumerate(products, start=1):
            line = locale.get_text(
                "admin.warehouse.product_line",
                idx=idx,
                name=product_names.get(product.id) or product.name,
                available=(product.stock or 0) - (product.reserved or 0),
                reserved=product.reserved or 0,
                unit=locale.get_unit(product.unit),
            )
            lines.append(line)

        header = locale.get_text("admin.warehouse.products_header")
        return f"{title}\n\n{header}\n" + "\n".join(lines)

    @staticmethod
    def _build_dashboard_text(
        locale: Locale,
        title: str,
        categories: list,
        products: list,
        category_names: dict[int, str],
        product_names: dict[int, str],
    ) -> str:
        """Дашборд склада: все товары по категориям (в наличии / заморожено).

        Если список не помещается в сообщение — обрезаем и добавляем
        пометку «… и ещё N товаров».
        """
        if not products:
            return title

        # Группируем товары по категориям (None — без категории)
        products_by_cat: dict[int | None, list] = {}
        for p in products:
            products_by_cat.setdefault(p.category_id, []).append(p)

        lines: list[str] = []
        total = len(products)
        shown = 0
        limit = 3800  # запас под заголовок и пометку об обрезке
        current_len = len(title)
        truncated = False

        def try_add(line: str) -> bool:
            nonlocal current_len
            if current_len + len(line) + 1 > limit:
                return False
            lines.append(line)
            current_len += len(line) + 1
            return True

        def product_line(idx: int, p) -> str:
            return locale.get_text(
                "admin.warehouse.product_line",
                idx=idx,
                name=product_names.get(p.id) or p.name,
                available=(p.stock or 0) - (p.reserved or 0),
                reserved=p.reserved or 0,
                unit=locale.get_unit(p.unit),
            )

        for cat in categories:
            if truncated:
                break
            cat_products = products_by_cat.get(cat.id, [])
            if not cat_products:
                continue
            if not try_add(f"\n📁 {category_names.get(cat.id, cat.name)}"):
                truncated = True
                break
            for idx, p in enumerate(cat_products, 1):
                if not try_add(product_line(idx, p)):
                    truncated = True
                    break
                shown += 1

        # Товары без категории
        no_cat = products_by_cat.get(None, [])
        if not truncated and no_cat and try_add(f"\n📁 {locale.get_text('admin.warehouse.no_category')}"):
            for idx, p in enumerate(no_cat, 1):
                if not try_add(product_line(idx, p)):
                    truncated = True
                    break
                shown += 1

        text = title + ("\n" + "\n".join(lines) if lines else "")
        if truncated:
            text += f"\n\n{locale.get_text('admin.warehouse.truncated', count=total - shown)}"
        return text

