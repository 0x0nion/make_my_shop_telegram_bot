# handlers/admin/shop/catalog.py
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_bot.handlers.admin.utils import parse_id, self_destruct
from shopcrm_bot.locales import Locale
from shopcrm_core.locales.units import DEFAULT_UNIT
from shopcrm_bot.ui import UIManager
from shopcrm_core.services.admin_shop_service import AdminShopService
from shopcrm_core.services.validation import validate_name
from shopcrm_bot.ui.presenters.admin import AdminUI
from shopcrm_bot.states.admin_states import AdminState

admin_catalog_router = Router()
logger = logging.getLogger(__name__)


@admin_catalog_router.callback_query(F.data == "admin_catalog_start")
async def catalog_root(
        event: CallbackQuery,
        admin_service: AdminShopService,
        admin_repo: AdminRepository,
        user: User,
        locale: Locale
):
    """Единственная точка старта сессии: синхронизация через сервис + открытие корня каталога."""
    await event.answer()
    await admin_service.start_editing_session(admin_id=event.from_user.id)

    await AdminUI.show_shop_catalog_menu(
        event=event,
        admin_repo=admin_repo,
        current_cat_id=None,
        user=user,
        locale=locale
    )


@admin_catalog_router.callback_query(F.data.startswith("admin_catalog_"))
async def handle_catalog_navigation(
    call: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Хендлер перехода по категориям (вложенные и возврат назад)."""
    await call.answer()

    raw_id = call.data.split("_")[-1]
    current_cat_id = int(raw_id) if raw_id.isdigit() else None

    await AdminUI.show_shop_catalog_menu(
        event=call,
        admin_repo=admin_repo,
        current_cat_id=current_cat_id,
        user=user,
        locale=locale,
    )


# ==================== УПРАВЛЕНИЕ КАТАЛОГОМ И ТОВАРАМИ ====================

@admin_catalog_router.callback_query(F.data == "admin_edit_cat:save_shop")
async def catalog_save_session(
    callback: CallbackQuery,
    admin_service: AdminShopService,
    locale: Locale
):
    """Сохранение изменений сессии магазина."""
    await callback.answer()
    await admin_service.save_editing_session(admin_id=callback.from_user.id)

    await UIManager.show(
        event=callback,
        text=locale.get_text("admin.shop_settings") + locale.get_text("admin.shop_updated"),
        reply_markup=locale.keyboards.build(
            "admin.shop_settings",
            callbacks={"back": "admin_main_menu"}
        ),
    )


@admin_catalog_router.callback_query(F.data.startswith("admin_edit_cat:add_cat_"))
async def catalog_start_add_category(
    callback: CallbackQuery,
    state: FSMContext,
    locale: Locale
):
    """Запуск процесса добавления подкатегории."""
    await callback.answer()
    raw_id = callback.data.split("_").pop()
    parent_id = parse_id(raw_id)

    await state.update_data(
        parent_id=parent_id,
        menu_message_id=callback.message.message_id
    )
    await state.set_state(AdminState.add_category)

    back_callback = f"admin_catalog_{raw_id}"
    reply_markup = locale.keyboards.get_back_kb(back_callback)

    await UIManager.show(
        event=callback,
        text=locale.get_text("catalog.enter_category_name"),
        reply_markup=reply_markup,
    )


@admin_catalog_router.callback_query(F.data.startswith("admin_edit_cat:del_cat_"))
async def catalog_delete_category(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale
):
    """Удаление категории."""
    await callback.answer()
    category_id_to_del = int(callback.data.split("_").pop())

    target_category = await admin_repo.get_category_by_id(
        category_id=category_id_to_del,
        use_temp=True,
        admin_id=callback.from_user.id,
    )
    parent_id = target_category.parent_id if target_category else None

    await admin_repo.delete_category(
        category_id=category_id_to_del,
        use_temp=True,
        admin_id=callback.from_user.id
    )

    await AdminUI.show_shop_catalog_menu(
        event=callback,
        admin_repo=admin_repo,
        current_cat_id=parent_id,
        user=user,
        locale=locale
    )


@admin_catalog_router.callback_query(F.data.startswith("admin_edit_cat:add_tittle_"))
async def catalog_start_add_description(
    callback: CallbackQuery,
    state: FSMContext,
    locale: Locale
):
    """Запуск процесса добавления/редактирования описания категории."""
    await callback.answer()
    raw_id = callback.data.split("_").pop()
    parent_id = parse_id(raw_id)

    await state.update_data(
        category_id=parent_id,
        menu_message_id=callback.message.message_id
    )
    await state.set_state(AdminState.edit_category_description)

    back_callback = f"admin_catalog_{raw_id}"
    reply_markup = locale.keyboards.get_back_kb(back_callback)

    await UIManager.show(
        event=callback,
        text=locale.get_text("catalog.enter_category_desc"),
        reply_markup=reply_markup,
    )


@admin_catalog_router.callback_query(F.data.startswith("admin_edit_cat:del_tittle_"))
async def catalog_delete_description(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale
):
    """Удаление описания категории."""
    await callback.answer()
    raw_id = callback.data.split("_").pop()
    parent_id = parse_id(raw_id)
    target_entity_id = parent_id if parent_id is not None else 0

    await admin_repo.delete_temp_locale_for_all_languages(
        entity_id=target_entity_id,
        entity_type="category_description",
        admin_id=callback.from_user.id,
    )

    await AdminUI.show_shop_catalog_menu(
        event=callback,
        admin_repo=admin_repo,
        current_cat_id=parent_id,
        user=user,
        locale=locale
    )


@admin_catalog_router.callback_query(F.data.startswith("admin_edit_cat:add_item_"))
async def catalog_add_product(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale
):
    """Быстрое создание товара по умолчанию в текущей категории."""
    raw_id = callback.data.split("_").pop()
    parent_id = parse_id(raw_id)

    default_name = locale.get_text("catalog.default_product_name")
    default_desc = locale.get_text("catalog.default_product_desc")

    await admin_repo.create_product(
        name=default_name,
        description=default_desc,
        price=0.0,
        category_id=parent_id,
        image_id=None,
        unit=DEFAULT_UNIT.value,
        use_temp=True,
        admin_id=callback.from_user.id,
    )

    await AdminUI.show_shop_catalog_menu(
        event=callback,
        admin_repo=admin_repo,
        current_cat_id=parent_id,
        user=user,
        locale=locale
    )

    alert_text = locale.get_text("alerts.product_created")
    await callback.answer(alert_text)


@admin_catalog_router.callback_query(F.data.startswith("admin_edit_cat:del_item_"))
async def catalog_delete_product(
    callback: CallbackQuery,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale
):
    """Удаление товара."""
    await state.clear()
    product_id = int(callback.data.split("_").pop())

    product = await admin_repo.get_product_by_id(
        product_id=product_id,
        use_temp=True,
        admin_id=callback.from_user.id,
    )
    category_id = product.category_id if product else None

    await admin_repo.delete_product(
        product_id=product_id,
        use_temp=True,
        admin_id=callback.from_user.id
    )

    await AdminUI.show_shop_catalog_menu(
        event=callback,
        admin_repo=admin_repo,
        current_cat_id=category_id,
        user=user,
        locale=locale
    )

    alert_text = locale.get_text("alerts.product_deleted")
    await callback.answer(alert_text)


# ==================== СОСТОЯНИЯ (FSM) ====================

@admin_catalog_router.message(AdminState.add_category, F.text)
async def process_add_category(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        locale: Locale,
        user: User,
):
    """Сохранение новой категории из текстового сообщения."""
    category_name = message.text.strip()
    user_data = await state.get_data()
    parent_id = user_data.get("parent_id")
    menu_message_id = user_data.get("menu_message_id", None)

    error = validate_name(category_name, lang=user.language)
    if error:
        err = await message.answer(error)
        await self_destruct(message=err, seconds=3)
        return

    await admin_repo.create_category(
        name=category_name,
        parent_id=parent_id,
        use_temp=True,
        admin_id=message.from_user.id,
    )
    await state.clear()
    await self_destruct(message=message, seconds=0)

    await AdminUI.show_shop_catalog_menu(
        event=message,
        admin_repo=admin_repo,
        current_cat_id=parent_id,
        user=user,
        locale=locale,
        message_id_to_edit=menu_message_id,
    )


@admin_catalog_router.message(AdminState.edit_category_description, F.text)
async def process_edit_category_description(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
        locale: Locale
):
    """Сохранение описания категории из текстового сообщения."""
    desc_text = message.text.strip()
    user_data = await state.get_data()
    category_id = user_data.get("category_id")
    menu_message_id = user_data.get("menu_message_id")

    target_entity_id = category_id if category_id is not None else 0

    await admin_repo.update_temp_locale_for_all_languages(
        entity_id=target_entity_id,
        entity_type="category_description",
        text=desc_text,
        admin_id=message.from_user.id,
    )

    await state.clear()
    await self_destruct(message=message, seconds=0)

    if menu_message_id:
        await AdminUI.show_shop_catalog_menu(
            event=message,
            admin_repo=admin_repo,
            current_cat_id=category_id,
            user=user,
            message_id_to_edit=menu_message_id,
            locale=locale
        )