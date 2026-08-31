# handlers/admin/main.py
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from locales.locale import Locale
from src.core.constants import OrderStatus
from src.ui.presenters.admin import AdminUI

admin_main_router = Router()
logger = logging.getLogger(__name__)


@admin_main_router.message(Command("admin"))
@admin_main_router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu(
        event: Message | CallbackQuery,
        admin_repo: AdminRepository,
        locale: Locale
):
    if isinstance(event, CallbackQuery):
        await event.answer()

    new_orders_count = await admin_repo.get_new_orders_count(
            status=OrderStatus.PENDING
        )

    await AdminUI.show_admin_main_menu(
        event=event,
        new_orders_count=new_orders_count,
        locale=locale
    )


# ###########################

# @admin_main_router.callback_query(F.data == "admin_shop_settings")
# async def cb_shop_settings(callback: CallbackQuery, user: User):
#     """Открытие подменю 'Настройка магазина'."""
#     locale = Locale(user.language)
#
#     markup = locale.keyboards.get_shop_settings_kb()
#     title_text = locale.get_text("admin.main_menu")
#     text = f"{title_text}\n\n⚙️ <b>Настройка магазина:</b>"
#
#     await UIManager.show(
#         event=callback,
#         text=text,
#         reply_markup=markup,
#     )
#
#
# @admin_main_router.callback_query(F.data == "admin_shop_start")
# async def cb_open_shop_root(
#     callback: CallbackQuery,
#     admin_service: AdminShopService,
#     admin_repo: AdminRepository,
#     user: User
# ):
#     """Единственная точка старта сессии: синхронизация через сервис + открытие корня каталога."""
#     await admin_service.start_editing_session(admin_id=callback.from_user.id)
#     await render_shop_menu(callback, admin_repo, current_cat_id=None, user=user)
#     await callback.answer()
#
#
# @admin_main_router.callback_query(F.data == "admin_save_shop")
# async def cb_admin_save(
#     callback: CallbackQuery,
#     admin_service: AdminShopService,
#     user: User
# ):
#     """Сохранение изменений через сервис."""
#     await admin_service.save_editing_session(admin_id=callback.from_user.id)
#     await show_admin_panel(
#         callback, user=user, is_saved=True
#     )


@admin_main_router.callback_query(
    F.data.startswith("admin_")
    & ~F.data.startswith("admin_shop")
    & ~F.data.startswith("admin_add")
    & ~F.data.startswith("admin_del")
    & ~F.data.startswith("admin_item")
    & ~F.data.startswith("admin_edit")
    & ~F.data.startswith("admin_set")
    & ~F.data.startswith("admin_save")
    & ~F.data.startswith("admin_mainmenu")
    & ~F.data.startswith("admin_greeting")
    & ~F.data.startswith("admin_edit_wel")
    & ~F.data.startswith("admin_order")     # <-- Исключаем все действия с заказами
)
async def catch_other_admin_actions(callback: CallbackQuery, user: User):
    """Безопасная заглушка для нереализованных разделов админки (без ложных срабатываний)."""
    parts = callback.data.split("_")
    action = parts[1] if len(parts) > 1 else "default"

    locale = Locale(user.language)

    alert_message = (
        locale.get_text(f"admin.alerts.{action}")
        if locale.has_text(f"admin.alerts.{action}")
        else locale.get_text("admin.alerts.default")
    )

    await callback.answer(alert_message, show_alert=True)