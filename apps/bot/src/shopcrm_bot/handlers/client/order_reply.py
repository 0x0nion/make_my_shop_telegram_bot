# handlers/client/order_reply.py
import logging
from contextlib import suppress
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    Message,
)

from shopcrm_core.db.models import User
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)

client_reply_router = Router()


class ClientReplyStates(StatesGroup):
    waiting_for_reply = State()


@client_reply_router.callback_query(F.data.startswith("client_reply_order:"))
async def client_start_reply(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    user: User,
):
    """Клиент нажал кнопку "Ответить администратору" под сообщением по заказу."""
    try:
        parts = callback.data.split(":")
        order_id = int(parts[1])
    except (IndexError, ValueError):
        logger.warning(f"[REPLY HANDLER] Invalid reply callback: {callback.data}")
        await callback.answer()
        return

    # Проверяем принадлежность заказа пользователю
    locale = Locale(user.language)
    order = await user_repo.get_order_with_items(order_id, user.id)
    if not order:
        await callback.answer(locale.get_text("client.user_order_not_found"), show_alert=True)
        return

    # Клавиатура «Назад» для отмены ввода ответа
    kb = locale.keyboards
    cancel_kb = kb.get_back_kb("client_cancel_reply")

    # 1. Рендерим меню ввода
    msg = await UIManager.show(
        event=callback,
        text=locale.get_text("client.client_reply_prompt", order_id=order_id),
        reply_markup=cancel_kb,
    )

    # 2. Сохраняем ID сообщения бота для последующего редактирования
    main_msg_id = msg.message_id if msg else callback.message.message_id

    await state.set_state(ClientReplyStates.waiting_for_reply)
    await state.update_data(
        order_id=order_id,
        main_message_id=main_msg_id,
    )


@client_reply_router.callback_query(
    F.data == "client_cancel_reply", ClientReplyStates.waiting_for_reply
)
async def client_cancel_reply(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
):
    """Отмена ввода ответа клиентом."""
    await state.clear()
    locale = Locale(user.language)

    await UIManager.show(
        event=callback,
        text=locale.get_text("client.client_reply_cancelled"),
        reply_markup=None,
    )


@client_reply_router.message(ClientReplyStates.waiting_for_reply)
async def client_send_reply(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    user: User,
    admin_ids: list[int],
):
    """Получает текст от клиента, сохраняет в историю заказа и уведомляет администраторов."""
    locale = Locale(user.language)

    data = await state.get_data()
    order_id = data.get("order_id")
    main_message_id = data.get("main_message_id")

    # Удаляем входящее текстовое сообщение пользователя, чтобы чат оставался чистым
    with suppress(TelegramBadRequest):
        await message.delete()

    await state.clear()

    if not order_id:
        await UIManager.show(
            event=message,
            text=locale.get_text("client.client_reply_session_error"),
            message_id_to_edit=main_message_id,
        )
        return

    # Формируем запись сообщения клиента с timezone-aware UTC
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    message_record = {
        "sender": "client",
        "text": message.text,
        "time": now_str,
    }

    # Сохраняем в историю заказа через метод миксина
    updated_order = await user_repo.append_order_chat_history(
        order_id=order_id,
        user_id=message.from_user.id,
        message_record=message_record,
    )

    if not updated_order:
        await UIManager.show(
            event=message,
            text=locale.get_text("client.client_reply_not_found"),
            message_id_to_edit=main_message_id,
        )
        return

    # Редактируем то самое сообщение бота, передавая main_message_id
    await UIManager.show(
        event=message,
        text=locale.get_text("client.client_reply_success"),
        message_id_to_edit=main_message_id,
    )

    # Уведомление админа — на языке админа
    for admin_id in admin_ids:
        try:
            admin_user = await user_repo.get_user(admin_id)
            admin_lang = admin_user.language if admin_user and admin_user.language else "ru"
            admin_locale = Locale(admin_lang)

            admin_kb = admin_locale.keyboards.build("admin.order_notification", order_id=order_id)
            admin_text = admin_locale.get_text("client.admin_notify_client_reply", order_id=order_id)

            await message.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=admin_kb,
            )
        except Exception as e:
            logger.error(
                f"[CLIENT REPLY] Failed to notify admin {admin_id}: {e}"
            )