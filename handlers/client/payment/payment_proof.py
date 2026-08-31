# handlers/client/payment/payment_proof.py
import asyncio
import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.models import User
from database.repositories.admin_repo import AdminRepository
from database.repositories.user_repo import UserRepository
from locales.locale import Locale
from src.core.constants import OrderStatus, PaymentProofType
from src.core.ui import UIManager
from src.services.notification_service import notify_admins_about_payment
from state.user_states import UserPaymentState

logger = logging.getLogger(__name__)

user_payment_router = Router()


async def safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """Удаляет сообщение с обработкой ошибок и логированием."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as err:
        logger.warning(
            f"[DeleteMsg Error] Chat: {chat_id}, Msg: {message_id} -> {err.message}"
        )
    except Exception as e:
        logger.error(
            f"[DeleteMsg Unexpected] Chat: {chat_id}, Msg: {message_id} -> {e}"
        )
    return False


async def delete_message_after_delay(
    chat_id: int, message_id: int, bot: Bot, delay: int = 20
):
    """Фоновая задача для удаления временного сообщения."""
    await asyncio.sleep(delay)
    await safe_delete_message(bot=bot, chat_id=chat_id, message_id=message_id)


@user_payment_router.callback_query(F.data.startswith("user_pay_confirm:"))
async def start_order_payment(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    user: User,
):
    """Вызывается при нажатии кнопки '✅ Я оплатил'."""
    locale = Locale(user.language)
    kb = locale.keyboards

    order_id = int(callback.data.split(":")[1])
    order = await user_repo.get_order_with_items(order_id, callback.from_user.id)

    if not order or order.is_paid or OrderStatus.is_final(order.status):
        await callback.answer(locale.get_text("client.order_not_found"), show_alert=True)
        return

    instruction_text = locale.get_text("client.payment_instruction")
    cancel_kb = kb.get_kb("cancel_reply")

    ui_msg = await UIManager.show(
        event=callback,
        text=instruction_text,
        reply_markup=cancel_kb,
    )

    instruction_msg_id = (
        ui_msg.message_id
        if ui_msg
        else (callback.message.message_id if callback.message else None)
    )
    await state.update_data(
        active_order_id=order_id, instruction_msg_id=instruction_msg_id
    )
    await state.set_state(UserPaymentState.waiting_for_proof)
    await callback.answer()


@user_payment_router.callback_query(F.data.startswith("user_pay_cash:"))
async def process_pay_cash(
    callback: CallbackQuery,
    bot: Bot,
    user_repo: UserRepository,
    user: User,
):
    """Вызывается при выборе оплаты наличными курьеру."""
    locale = Locale(user.language)

    order_id = int(callback.data.split(":")[1])

    # 1. Записываем тип и маркер подтверждения
    updated_order = await user_repo.attach_payment_proof(
        order_id=order_id,
        user_id=callback.from_user.id,
        proof_type=PaymentProofType.CASH.value,
        proof_content="cash",
    )

    if not updated_order:
        await callback.answer(locale.get_text("order_not_found"), show_alert=True)
        return

    # 2. Обновляем статус заказа до 'processing' через репозиторий
    await user_repo.update_order_status(
        order_id=order_id,
        status=OrderStatus.PROCESSING.value,
    )

    await callback.answer()

    confirm_msg = await UIManager.show(
        event=callback,
        text=locale.get_text("payment_cash_accepted"),
    )

    if confirm_msg:
        asyncio.create_task(
            delete_message_after_delay(
                chat_id=confirm_msg.chat.id,
                message_id=confirm_msg.message_id,
                bot=bot,
                delay=20,
            )
        )


@user_payment_router.message(
    UserPaymentState.waiting_for_proof,
    F.photo | F.text | F.document,
)
async def process_payment_proof_input(
    message: Message,
    state: FSMContext,
    bot: Bot,
    user_repo: UserRepository,
    admin_repo: AdminRepository,
    user: User,
):
    """Единый обработчик скриншота, файла или хэша транзакции."""
    locale = Locale(user.language)

    data = await state.get_data()
    order_id: Optional[int] = data.get("active_order_id")
    instruction_msg_id: Optional[int] = data.get("instruction_msg_id")

    # Очищаем пользовательский ввод
    await safe_delete_message(
        bot=bot, chat_id=message.chat.id, message_id=message.message_id
    )

    if instruction_msg_id:
        await safe_delete_message(
            bot=bot, chat_id=message.chat.id, message_id=instruction_msg_id
        )

    if not order_id:
        await state.clear()
        expired_msg = await UIManager.show(
            event=message,
            text=locale.get_text("client.session_expired"),
        )
        if expired_msg:
            asyncio.create_task(
                delete_message_after_delay(
                    chat_id=expired_msg.chat.id,
                    message_id=expired_msg.message_id,
                    bot=bot,
                    delay=15,
                )
            )
        return

    proof_type = PaymentProofType.TX_HASH.value
    proof_content = ""

    if message.photo:
        proof_type = PaymentProofType.PHOTO.value
        proof_content = message.photo[-1].file_id
    elif message.document:
        proof_type = PaymentProofType.DOCUMENT.value
        proof_content = message.document.file_id
    elif message.text:
        proof_type = PaymentProofType.TX_HASH.value
        proof_content = message.text.strip()

    updated_order = await user_repo.attach_payment_proof(
        order_id=order_id,
        user_id=message.from_user.id,
        proof_type=proof_type,
        proof_content=proof_content,
    )

    await state.clear()

    if not updated_order:
        err_msg = await UIManager.show(
            event=message,
            text=locale.get_text("client.payment_error_or_already_paid"),
        )
        if err_msg:
            asyncio.create_task(
                delete_message_after_delay(
                    chat_id=err_msg.chat.id,
                    message_id=err_msg.message_id,
                    bot=bot,
                    delay=15,
                )
            )
        return

    # Вызов сервиса уведомления админов только для онлайн-чеков/хэшей
    asyncio.create_task(
        notify_admins_about_payment(
            bot=bot,
            admin_repo=admin_repo,
            order_id=order_id,
        )
    )

    confirm_msg = await UIManager.show(
        event=message,
        text=locale.get_text("client.payment_proof_accepted"),
    )

    if confirm_msg:
        asyncio.create_task(
            delete_message_after_delay(
                chat_id=confirm_msg.chat.id,
                message_id=confirm_msg.message_id,
                bot=bot,
                delay=20,
            )
        )


@user_payment_router.message(UserPaymentState.waiting_for_proof)
async def process_invalid_payment_proof(
    message: Message,
    bot: Bot,
    user: User,
):
    """Отлавливает некорректный контент (стикеры, аудио, видео) в состоянии ожидания чека."""
    locale = Locale(user.language)

    await safe_delete_message(
        bot=bot, chat_id=message.chat.id, message_id=message.message_id
    )

    err_msg = await UIManager.show(
        event=message,
        text=locale.get_text("client.invalid_payment_proof_type"),
    )
    if err_msg:
        asyncio.create_task(
            delete_message_after_delay(
                chat_id=err_msg.chat.id,
                message_id=err_msg.message_id,
                bot=bot,
                delay=10,
            )
        )