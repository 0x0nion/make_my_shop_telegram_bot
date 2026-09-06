import asyncio
import logging
from typing import Optional

from aiogram import F, Router, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail
from locales.locale import Locale
from src.core.constants import OrderStatus

logger = logging.getLogger(__name__)

admin_payment_request_router = Router()


# --- Вспомогательные функции ---

def _get_client_lang(client_user: Optional[User]) -> str:
    """Возвращает язык клиента из БД с дефолтом на 'ru'."""
    if not client_user or not client_user.language:
        return "ru"
    return client_user.language


def _get_client_tg_id(client_user: User) -> int:
    """Возвращает Telegram ID пользователя из модели БД."""
    return client_user.id


async def _fetch_payment_details(admin_repo: AdminRepository, lang: str) -> str:
    """Безопасно извлекает реквизиты оплаты для указанного языка."""
    payment_details_obj = await admin_repo.get_locale_text(
        entity_id=0,
        entity_type="payment_details",
        language_code=lang,
        use_temp=False,
    )

    if hasattr(payment_details_obj, "text"):
        return payment_details_obj.text
    if isinstance(payment_details_obj, str):
        return payment_details_obj
    return Locale(lang).get_text("admin.orders.payment_details_fallback")


async def _safe_edit_or_caption(message: Message, text: str) -> None:
    """Безопасно обновляет текст или подпись сообщения в зависимости от наличия медиа."""
    try:
        if message.photo or message.document or message.video:
            await message.edit_caption(caption=text, reply_markup=None)
        else:
            await message.edit_text(text=text, reply_markup=None)
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось отредактировать сообщение {message.message_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения {message.message_id}: {e}")


# --- Хендлеры ---

@admin_payment_request_router.callback_query(F.data.startswith("admin_order_request_payment:"))
async def process_admin_request_payment(
        callback: CallbackQuery,
        bot: Bot,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    admin_locale = Locale(lang=_get_client_lang(user))
    try:
        order_id = int(parts[1])
        status = parts[2] if len(parts) > 2 else "all"
        page = int(parts[3]) if len(parts) > 3 else 1
    except (IndexError, ValueError):
        await callback.answer(admin_locale.get_text("admin.orders.request_parse_error"), show_alert=True)
        return

    order = await admin_repo.get_order_by_id(order_id)
    if not order or not order.user:
        await callback.answer(admin_locale.get_text("admin.orders.request_order_not_found"), show_alert=True)
        return

    client_lang = _get_client_lang(order.user)
    client_tg_id = _get_client_tg_id(order.user)
    payment_details = await _fetch_payment_details(admin_repo, client_lang)

    locale = Locale(lang=client_lang)

    try:
        client_text = locale.format_order(
            order=order,
            template_key="client.order_payment_request_text",
            payment_details=payment_details,
        )
    except KeyError as e:
        logger.error(f"Ошибка форматирования шаблона 'order_payment_request_text': отсутствует ключ {e}")
        await callback.answer(admin_locale.get_text("admin.orders.format_error"), show_alert=True)
        return

    client_kb = locale.keyboards
    client_reply_markup = client_kb.get_order_payment_request_kb(order_id=order.id)

    # 1. Отправка клиенту
    try:
        await bot.send_message(
            chat_id=client_tg_id,
            text=client_text,
            reply_markup=client_reply_markup,
            parse_mode="HTML",
        )
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.warning(f"Не удалось отправить запрос оплаты пользователю {client_tg_id}: {e}")
        await callback.answer(admin_locale.get_text("admin.orders.send_failed"), show_alert=True)
        return
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {client_tg_id}: {e}")
        await callback.answer(admin_locale.get_text("admin.orders.send_error"), show_alert=True)
        return

    # 2. Обновление статуса в БД после отправки
    order.status = OrderStatus.PAYMENT_REQUESTED.value
    await admin_repo.update_order(order)

    # 3. Перерисовка карточки у админа
    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )
    await callback.answer(admin_locale.get_text("admin.orders.payment_requested_sent"), show_alert=False)


@admin_payment_request_router.callback_query(F.data.startswith("admin_pay_approve:"))
async def process_approve_payment(
        callback: CallbackQuery,
        bot: Bot,
        admin_repo: AdminRepository,
        user: User,
):
    admin_locale = Locale(lang=_get_client_lang(user))

    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer(admin_locale.get_text("admin.orders.invalid_data"), show_alert=True)
        return

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer(admin_locale.get_text("admin.orders.order_not_found"), show_alert=True)
        return

    if order.is_paid:
        await callback.answer(admin_locale.get_text("admin.orders.order_already_processed"), show_alert=True)
        return

    # 1. Изменение статуса и флага оплаты
    order.is_paid = True
    order.status = OrderStatus.PROCESSING.value
    await admin_repo.update_order(order)

    await callback.answer(admin_locale.get_text("admin.orders.payment_approved_alert"), show_alert=False)

    # 2. Уведомление клиента
    if order.user:
        client_lang = _get_client_lang(order.user)
        client_locale = Locale(lang=client_lang)
        client_tg_id = _get_client_tg_id(order.user)

        raw_template = client_locale.get_text("client.user_payment_confirmed_notification")
        formatted_text = raw_template.format(id=order_id) if raw_template != "XXX" else client_locale.get_text("admin.orders.client_confirmed_fallback", id=order_id)

        try:
            await bot.send_message(
                chat_id=client_tg_id,
                text=formatted_text,
                parse_mode="HTML",
            )
        except TelegramBadRequest as err:
            logger.warning(f"Не удалось отправить уведомление пользователю {client_tg_id}: {err.message}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {client_tg_id}: {e}")

    # 3. Обновление карточки админа и удаление через 3 секунды
    status_text = admin_locale.get_text("admin.orders.pay_status_accepted")
    if isinstance(callback.message, Message):
        await _safe_edit_or_caption(callback.message, status_text)

        await asyncio.sleep(3)
        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение {callback.message.message_id}: {e}")


@admin_payment_request_router.callback_query(F.data.startswith("admin_pay_reject:"))
async def process_reject_payment(
        callback: CallbackQuery,
        bot: Bot,
        admin_repo: AdminRepository,
        user: User,
):
    admin_locale = Locale(lang=_get_client_lang(user))

    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer(admin_locale.get_text("admin.orders.invalid_data"), show_alert=True)
        return

    order = await admin_repo.get_order_by_id(order_id)
    if not order or not order.user:
        await callback.answer(admin_locale.get_text("admin.orders.order_not_found"), show_alert=True)
        return

    client_lang = _get_client_lang(order.user)
    client_tg_id = _get_client_tg_id(order.user)

    payment_details = await _fetch_payment_details(admin_repo, client_lang)
    client_locale = Locale(lang=client_lang)

    raw_reject_msg = client_locale.get_text("client.user_payment_rejected_notification")
    reject_msg = raw_reject_msg.format(id=order_id) if raw_reject_msg != "XXX" else client_locale.get_text("admin.orders.client_rejected_fallback", id=order_id)

    try:
        payment_form_msg = client_locale.format_order(
            order=order,
            template_key="client.order_payment_request_text",
            payment_details=payment_details,
        )
    except KeyError as e:
        logger.error(f"Ошибка форматирования шаблона 'order_payment_request_text': отсутствует ключ {e}")
        await callback.answer(admin_locale.get_text("admin.orders.format_error"), show_alert=True)
        return

    full_client_text = f"{reject_msg}\n\n{payment_form_msg}"

    client_kb = client_locale.keyboards
    client_reply_markup = client_kb.get_order_payment_request_kb(order_id=order.id)

    # 1. Отправка повторного запроса клиенту
    try:
        await bot.send_message(
            chat_id=client_tg_id,
            text=full_client_text,
            reply_markup=client_reply_markup,
            parse_mode="HTML",
        )
    except (TelegramForbiddenError, TelegramBadRequest) as err:
        logger.warning(f"Не удалось отправить уведомление пользователю {client_tg_id}: {err}")
        await callback.answer(admin_locale.get_text("admin.orders.resend_failed"), show_alert=True)
        return
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {client_tg_id}: {e}")
        await callback.answer(admin_locale.get_text("admin.orders.notify_error"), show_alert=True)
        return

    # 2. Обновление состояния в БД после успешной отправки.
    # Очищаем устаревшие данные отклонённого чека: цикл «запрос → ответ»
    # перезапускается, и кнопка «Запросить оплату» снова доступна у админа,
    # если клиент проигнорирует повторно отправленную форму.
    order.is_paid = False
    order.status = OrderStatus.PAYMENT_REQUESTED.value
    order.payment_proof_type = None
    order.payment_proof = None
    await admin_repo.update_order(order)

    await callback.answer(admin_locale.get_text("admin.orders.payment_rejected_alert"), show_alert=False)

    # 3. Обновление плашки у админа и ее удаление через 3 сек
    status_text = admin_locale.get_text("admin.orders.pay_status_rejected")
    if isinstance(callback.message, Message):
        await _safe_edit_or_caption(callback.message, status_text)

        await asyncio.sleep(3)
        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение {callback.message.message_id}: {e}")