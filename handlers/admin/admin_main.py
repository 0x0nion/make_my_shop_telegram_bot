# handlers/admin/admin_main.py
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.show_admin_panel import show_admin_panel
from handlers.admin.shop.render_shop_menu import render_shop_menu
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from src.core.ui import UIManager
from src.services.admin_shop_service import AdminShopService

admin_main_router = Router()
logger = logging.getLogger(__name__)


@admin_main_router.message(Command("admin"))
@admin_main_router.callback_query(F.data == "admin")
async def cmd_admin_entry(
    event: Message | CallbackQuery, user: User
):
    """Единая точка входа в админ-панель (DRY)."""
    await show_admin_panel(event, user=user)


@admin_main_router.callback_query(F.data == "admin_shop_settings")
async def cb_shop_settings(callback: CallbackQuery, user: User):
    """Открытие подменю 'Настройка магазина'."""
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    markup = kb.get_shop_settings_kb()
    title_text = kb.get_text("welcome_title", "🔑 Панель администратора открыта:")
    text = f"{title_text}\n\n⚙️ <b>Настройка магазина:</b>"

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=markup,
    )


@admin_main_router.callback_query(F.data == "admin_shop_start")
async def cb_open_shop_root(
    callback: CallbackQuery,
    admin_service: AdminShopService,
    admin_repo: AdminRepository,
    user: User
):
    """Единственная точка старта сессии: синхронизация через сервис + открытие корня каталога."""
    await admin_service.start_editing_session(admin_id=callback.from_user.id)
    await render_shop_menu(callback, admin_repo, current_cat_id=None, user=user)
    await callback.answer()


@admin_main_router.callback_query(F.data == "admin_save_shop")
async def cb_admin_save(
    callback: CallbackQuery,
    admin_service: AdminShopService,
    user: User
):
    """Сохранение изменений через сервис."""
    await admin_service.save_editing_session(admin_id=callback.from_user.id)
    await show_admin_panel(
        callback, user=user, is_saved=True
    )


@admin_main_router.callback_query(F.data == "admin_mainmenu")
async def back_to_main_menu(
    callback: CallbackQuery, user: User
):
    await show_admin_panel(callback, user=user)


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

    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    alert_message = kb.get_text(f"alerts.{action}") or kb.get_text(
        "alerts.default", "Раздел в разработке..."
    )

    await callback.answer(alert_message, show_alert=True)