import logging
from contextlib import suppress
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import config
from database.repositories.user_repo import UserRepository
from src.core.ui import UIManager

logger = logging.getLogger(__name__)

client_reply_router = Router()


class ClientReplyStates(StatesGroup):
    waiting_for_reply = State()


@client_reply_router.callback_query(F.data.startswith("client_reply_order:"))
async def client_start_reply(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Клиент нажал кнопку "Ответить администратору" под сообщением по заказу."""
    parts = callback.data.split(":")
    order_id = int(parts[1])

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="client_cancel_reply"
                )
            ]
        ]
    )

    # 1. Рендерим меню ввода
    msg = await UIManager.show(
        event=callback,
        text=f"💬 <b>Ответ администратору (Заказ #{order_id})</b>\n\n"
        f"Введите текст вашего сообщения:",
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
async def client_cancel_reply(callback: CallbackQuery, state: FSMContext):
    """Отмена ввода ответа клиентом."""
    await state.clear()
    await UIManager.show(
        event=callback,
        text="❌ Отправка сообщения отменена.",
        reply_markup=None,
    )


@client_reply_router.message(ClientReplyStates.waiting_for_reply)
async def client_send_reply(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
):
    """Получает текст от клиента, сохраняет в историю заказа и уведомляет администраторов."""
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
            text="❌ Ошибка сессии. Попробуйте снова.",
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
            text="❌ Не удалось найти заказ или он недоступен.",
            message_id_to_edit=main_message_id,
        )
        return

    # Редактируем то самое сообщение бота, передавая main_message_id
    await UIManager.show(
        event=message,
        text="✅ Ваш ответ успешно отправлен администратору!",
        message_id_to_edit=main_message_id,
    )

    # Создаем кнопку для перехода прямо в карточку заказа
    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Открыть заказ",
                    callback_data=f"admin_order_view:{order_id}:all:1",
                )
            ]
        ]
    )

    for admin_id in config.ADMIN_ID:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"💬 <b>Новое сообщение в заказе #{order_id}</b>\n\n"
                f"Клиент написал ответ по заказу.",
                reply_markup=admin_kb,
            )
        except Exception as e:
            logger.error(
                f"[CLIENT REPLY] Failed to notify admin {admin_id}: {e}"
            )