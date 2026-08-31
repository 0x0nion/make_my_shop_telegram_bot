from aiogram.types import CallbackQuery, Message

from database.models import User
from database.repositories.admin_repo import AdminRepository
from locales.locale import Locale
from src.core.ui import UIManager
from src.ui.presenters.catalog import CatalogMenuPresenter


class AdminUI:
    @staticmethod
    async def show_admin_main_menu(
        event: Message | CallbackQuery,
        locale: Locale,
        new_orders_count: int = 0,
    ) -> None:
        """Главный экран админ-панели."""
        text = locale.get_text("admin.main_menu")

        orders_badge = f" ({new_orders_count} 🔴 )" if new_orders_count > 0 else ""

        reply_markup = locale.keyboards.build(
            "admin.main_menu",
            new_orders_count=orders_badge,
        )

        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
        )

    @staticmethod
    async def show_shop_catalog_menu(
            event: CallbackQuery | Message,
            admin_repo: AdminRepository,
            current_cat_id: int | None,
            user: User,
            locale: Locale,
            message_id_to_edit: int | None = None,
    ) -> None:
        """Универсальная и безопасная функция отрисовки интерфейса магазина через UIManager."""
        admin_id = event.from_user.id

        # 1. Получаем текущую категорию и её переводы из БД
        current_cat = None
        category_description = None
        root_description = None

        if current_cat_id:
            current_cat = await admin_repo.get_category_by_id(
                category_id=current_cat_id, use_temp=True, admin_id=admin_id
            )
            if current_cat:
                category_description = await admin_repo.get_locale_text(
                    entity_id=current_cat_id,
                    entity_type="category_description",
                    language_code=user.language,
                    use_temp=True,
                    admin_id=admin_id,
                )
        else:
            root_description = await admin_repo.get_locale_text(
                entity_id=0,
                entity_type="category_description",
                language_code=user.language,
                use_temp=True,
                admin_id=admin_id,
            )

        # 2. Забираем списки товаров и подкатегорий
        db_categories = await admin_repo.get_categories_by_parent(
            parent_id=current_cat_id, use_temp=True, admin_id=admin_id
        )
        db_products = await admin_repo.get_products_by_category(
            category_id=current_cat_id, use_temp=True, admin_id=admin_id
        )

        # 3. Собираем локализованные имена подкатегорий и текущей категории
        category_names: dict[int, str] = {}
        if current_cat:
            cat_name = await admin_repo.get_locale_text(
                entity_id=current_cat.id,
                entity_type="category_name",
                language_code=user.language,
                use_temp=True,
                admin_id=admin_id,
            )
            category_names[current_cat.id] = cat_name or current_cat.name

        for cat in db_categories:
            loc_name = await admin_repo.get_locale_text(
                entity_id=cat.id,
                entity_type="category_name",
                language_code=user.language,
                use_temp=True,
                admin_id=admin_id,
            )
            category_names[cat.id] = loc_name or cat.name

        # 4. Рендерим готовый экран и клавиатуру через Презентер
        text, reply_markup = CatalogMenuPresenter.render(
            locale=locale,
            current_cat=current_cat,
            current_cat_id=current_cat_id,
            db_categories=db_categories,
            db_products=db_products,
            category_names=category_names,
            category_description=category_description,
            root_description=root_description,
        )

        # 5. Отдаем на отрисовку
        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
            message_id_to_edit=message_id_to_edit,
        )