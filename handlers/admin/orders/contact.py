import logging
from datetime import datetime
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail
from src.core.ui import UIManager

logger = logging.getLogger(__name__)

order_contact_router = Router()

# Количество сообщений на одной странице пагинации чата
MESSAGES_PER_PAGE = 5


class AdminContactStates(StatesGroup):
    waiting_for_message = State()


def format_chat_history(chat_history: list | None, page: int = 1) -> tuple[str, InlineKeyboardMarkup | None]:
    """
    Форматирует историю переписки для отображения с пагинацией.
    """
    if not chat_history:
        return "<i>История переписки пуста.</i>\n\n", None

    total_messages = len(chat_history)
    total_pages = max(1, (total_messages + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE)
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * MESSAGES_PER_PAGE
    end_idx = start_idx + MESSAGES_PER_PAGE
    page_messages = chat_history[start_idx:end_idx]

    history_text = "📜 <b>История переписки:</b>\n" + "—" * 20 + "\n"

    for msg in page_messages:
        sender = msg.get("sender")
        text = msg.get("text", "")
        time_str = msg.get("time", "")

        if sender == "admin":
            author = "🧑‍💻 <b>Администратор</b>"
        else:
            author = "👤 <b>Клиент</b>"

        history_text += f"{author} <i>({time_str})</i>:\n{text}\n\n"

    history_text += "—" * 20 + f"\n📄 Страница {current_page} из {total_pages}\n\n"

    pagination_buttons = []
    if total_pages > 1:
        if current_page > 1:
            pagination_buttons.append(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_chat_page:{current_page - 1}")
            )
        if current_page < total_pages:
            pagination_buttons.append(
                InlineKeyboardButton(text="Вперед ➡️", callback_data=f"admin_chat_page:{current_page + 1}")
            )

    return history_text, pagination_buttons


@order_contact_router.callback_query(F.data.startswith("admin_order_contact_client:"))
async def process_contact_client_start(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    state: FSMContext,
):
    """
    Запрос у администратора текста для отправки клиенту с отображением истории переписки.
    Callback format: admin_order_contact_client:{order_id}:{status}:{page}
    """
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    order = await admin_repo.get_order_by_id(order_id)
    if not order or not order.user:
        await callback.answer("❌ Данные пользователя или сам заказ недоступны", show_alert=True)
        return

    chat_history = order.chat_history or []
    initial_chat_page = max(1, (len(chat_history) + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE)

    await state.set_state(AdminContactStates.waiting_for_message)
    await state.update_data(
        target_user_id=order.user.id,
        order_id=order_id,
        status=status,
        page=page,
        card_message_id=callback.message.message_id,
        chat_page=initial_chat_page,
    )

    history_str, nav_buttons = format_chat_history(chat_history, page=initial_chat_page)

    keyboard_rows = []
    if nav_buttons:
        keyboard_rows.append(nav_buttons)

    keyboard_rows.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_order_view:{order_id}:{status}:{page}")]
    )

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    text_content = (
        f"💬 <b>Связь с клиентом (Заказ #{order_id})</b>\n\n"
        f"{history_str}"
        f"Введите текст сообщения, который хотите отправить покупателю:"
    )

    # Используем UIManager для отрисовки экрана ввода сообщения
    await UIManager.show(
        event=callback,
        text=text_content,
        reply_markup=cancel_kb,
        message_id_to_edit=callback.message.message_id,
    )


@order_contact_router.callback_query(F.data.startswith("admin_chat_page:"))
async def process_chat_pagination(
    callback: CallbackQuery,
    state: FSMContext,
    admin_repo: AdminRepository,
):
    """
    Обработка переключения страниц истории переписки в режиме ввода сообщения.
    """
    data = await state.get_data()
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)

    if not order_id:
        await callback.answer("❌ Сессия устарела", show_alert=True)
        return

    target_chat_page = int(callback.data.split(":")[1])
    await state.update_data(chat_page=target_chat_page)

    order = await admin_repo.get_order_by_id(order_id)
    chat_history = order.chat_history if order else []

    history_str, nav_buttons = format_chat_history(chat_history, page=target_chat_page)

    keyboard_rows = []
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    keyboard_rows.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_order_view:{order_id}:{status}:{page}")]
    )

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    text_content = (
        f"💬 <b>Связь с клиентом (Заказ #{order_id})</b>\n\n"
        f"{history_str}"
        f"Введите текст сообщения, который хотите отправить покупателю:"
    )

    # Используем UIManager для пагинации (автоматически обработает «message is not modified»)
    await UIManager.show(
        event=callback,
        text=text_content,
        reply_markup=cancel_kb,
        message_id_to_edit=callback.message.message_id,
    )


@order_contact_router.message(AdminContactStates.waiting_for_message)
async def process_send_client_message(
    message: Message,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
):
    """
    Сохраняет сообщение админа в историю, отправляет клиенту,
    удаляет сообщение ввода и возвращает карточку заказа.
    """
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    card_message_id = data.get("card_message_id")

    await state.clear()

    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"[ADMIN CONTACT] Could not delete admin message: {e}")

    if not target_user_id or not order_id:
        return

    now_str = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
    message_record = {
        "sender": "admin",
        "text": message.text,
        "time": now_str,
    }

    await admin_repo.append_order_chat_history(order_id, message_record)

    client_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить администратору", callback_data=f"client_reply_order:{order_id}")]
        ]
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=f"💬 <b>Сообщение от администрации по заказу #{order_id}:</b>\n\n{message.text}",
            reply_markup=client_kb,
        )
    except Exception as e:
        logger.error(f"[ADMIN CONTACT] Failed to send message to user {target_user_id}: {e}")
        return

    await render_order_detail(
        event=message,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
        message_id_to_edit=card_message_id,
    )