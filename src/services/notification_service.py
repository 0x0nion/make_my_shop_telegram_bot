# services/notification_service.py
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from config import config as app_config
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import build_order_detail_text
from locales.locale import Locale
from src.core.constants import PaymentProofType

logger = logging.getLogger(__name__)


def get_payment_verify_kb(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура быстрого подтверждения/отклонения оплаты для администратора."""
    locale = Locale("ru")
    return locale.keyboards.build("admin.payment_verify", order_id=order_id)


async def notify_admins_about_payment(
    bot: Bot,
    admin_repo: AdminRepository,
    order_id: int,
):
    """Отправляет карточку заказа с прикреплённым чеком/текстом всем администраторам."""
    admin_ids: list[int] = app_config.ADMIN_ID

    text, order = await build_order_detail_text(admin_repo, order_id)

    if not order:
        logger.warning(
            f"Заказ #{order_id} не найден при отправке уведомления администраторам."
        )
        return

    caption = Locale("ru").get_text("notifications.new_payment", order_id=order_id) + text
    reply_markup = get_payment_verify_kb(order_id)

    for admin_id in admin_ids:
        try:
            if order.payment_proof_type == PaymentProofType.PHOTO.value:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=order.payment_proof,
                    caption=caption,
                    reply_markup=reply_markup,
                )
            elif order.payment_proof_type == PaymentProofType.DOCUMENT.value:
                await bot.send_document(
                    chat_id=admin_id,
                    document=order.payment_proof,
                    caption=caption,
                    reply_markup=reply_markup,
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=caption,
                    reply_markup=reply_markup,
                )
        except Exception as e:
            logger.error(
                f"Не удалось отправить уведомление об оплате заказа #{order_id} админу {admin_id}: {e}"
            )