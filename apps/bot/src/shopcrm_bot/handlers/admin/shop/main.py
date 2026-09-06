# handlers/admin/shop/main.py
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery

from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager

admin_shop_main_router = Router()
logger = logging.getLogger(__name__)


@admin_shop_main_router.callback_query(F.data == "admin_shop_settings")
async def admin_shop_settings(
    event: CallbackQuery,
    locale: Locale,
):
    """Экран настроек магазина."""
    await event.answer()
    await UIManager.show(
        event=event,
        text=locale.get_text("admin.shop_settings"),
        reply_markup=locale.keyboards.build(
            "admin.shop_settings",
            callbacks={
                "back": "admin_main_menu"
            }
        ),
    )


# ################################################



# @admin_shop_main_router.callback_query(F.data == "admin_save_shop")
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