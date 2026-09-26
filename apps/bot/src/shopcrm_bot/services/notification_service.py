# services/notification_service.py
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from shopcrm_bot.config import config as app_config
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_core.services.order_service import build_order_detail_text
from shopcrm_bot.locales import Locale
from shopcrm_core.constants import PaymentProofType

logger = logging.getLogger(__name__)


def get_payment_verify_kb(order_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Клавиатура быстрого подтверждения/отклонения оплаты для администратора."""
    locale = Locale(lang)
    return locale.keyboards.build("admin.payment_verify", order_id=order_id)


async def notify_admins_about_payment(
    bot: Bot,
    admin_repo: AdminRepository,
    user_repo: UserRepository,
    order_id: int,
    admin_ids: list[int] | None = None,
):
    """Отправляет карточку заказа с прикреплённым чеком/текстом всем администраторам.

    Каждый администратор получает уведомление на своём сохранённом языке
    (EN — по умолчанию, если язык не задан).
    """
    admin_ids = admin_ids or app_config.ADMIN_ID

    for admin_id in admin_ids:
        try:
            admin_user = await user_repo.get_user(admin_id)
            admin_lang = admin_user.language if admin_user and admin_user.language else "en"

            text, order = await build_order_detail_text(admin_repo, order_id, lang=admin_lang)
            if not order:
                logger.warning(
                    f"Заказ #{order_id} не найден при отправке уведомления администраторам."
                )
                return

            caption = Locale(admin_lang).get_text(
                "notifications.new_payment", order_id=order_id
            ) + text
            reply_markup = get_payment_verify_kb(order_id, lang=admin_lang)

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


async def notify_admins_about_new_order(
    bot: Bot,
    admin_repo: AdminRepository,
    user_repo: UserRepository,
    order_id: int,
    admin_ids: list[int] | None = None,
):
    """Отправляет карточку нового заказа всем администраторам.

    Уведомление содержит детали заказа (покупатель, состав, итог, адрес)
    и кнопку «Перейти к заказу» (callback ``admin_order_view:{order_id}``).
    Каждый администратор получает уведомление на своём сохранённом языке
    (EN — по умолчанию, если язык не задан).
    """
    admin_ids = admin_ids or app_config.ADMIN_ID

    for admin_id in admin_ids:
        try:
            admin_user = await user_repo.get_user(admin_id)
            admin_lang = admin_user.language if admin_user and admin_user.language else "en"

            text, order = await build_order_detail_text(admin_repo, order_id, lang=admin_lang)
            if not order:
                logger.warning(
                    f"Заказ #{order_id} не найден при отправке уведомления администраторам."
                )
                return

            caption = Locale(admin_lang).get_text(
                "notifications.new_order", order_id=order_id
            ) + text
            reply_markup = Locale(admin_lang).keyboards.build(
                "admin.new_order", order_id=order_id
            )

            await bot.send_message(
                chat_id=admin_id,
                text=caption,
                reply_markup=reply_markup,
            )
        except Exception as e:
            logger.error(
                f"Не удалось отправить уведомление о новом заказе #{order_id} админу {admin_id}: {e}"
            )


async def notify_admins_about_cancellation(
    bot: Bot,
    user_repo: UserRepository,
    order_id: int,
    admin_ids: list[int] | None = None,
):
    """Уведомляет всех администраторов об отмене заказа клиентом.

    Каждый администратор получает уведомление на своём сохранённом языке
    (EN — по умолчанию, если язык не задан).
    """
    for admin_id in (admin_ids or app_config.ADMIN_ID):
        try:
            admin_user = await user_repo.get_user(admin_id)
            admin_lang = admin_user.language if admin_user and admin_user.language else "en"
            await bot.send_message(
                chat_id=admin_id,
                text=Locale(admin_lang).get_text(
                    "notifications.order_cancelled", order_id=order_id
                ),
            )
        except Exception as e:
            logger.error(
                f"Не удалось отправить уведомление об отмене заказа #{order_id} админу {admin_id}: {e}"
            )