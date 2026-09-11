import logging

from aiogram.types import CallbackQuery, Message

from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.services.order_service import build_order_detail_text
from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)


async def render_order_detail(
        event: CallbackQuery | Message,
        admin_repo: AdminRepository,
        user: User,
        order_id: int,
        status: str = "all",
        page: int = 1,
        message_id_to_edit: int | None = None,
):
    """
    Универсальная функция рендера карточки заказа с подгрузкой локализованного
    шаблона из locale.json и сборкой клавиатуры.
    """
    locale = Locale(user.language)
    kb = locale.keyboards

    text, order = await build_order_detail_text(admin_repo, order_id, lang=user.language)
    if not order:
        text_not_found = locale.get_text("admin.orders.not_found")
        await UIManager.show(
            event=event,
            text=text_not_found,
            reply_markup=kb.get_back_kb(f"admin_orders_page:{status}:{page}"),
            message_id_to_edit=message_id_to_edit,
        )
        return

    # Если чек оплаты — фото, показываем его сверху карточки (текст становится caption)
    photo = order.payment_proof if order.payment_proof_type == "photo" else None

    await UIManager.show(
        event=event,
        text=text,
        reply_markup=kb.get_order_detail_kb(order=order, status=status, page=page),
        photo=photo,
        message_id_to_edit=message_id_to_edit,
    )


