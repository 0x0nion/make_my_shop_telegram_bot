import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail

logger = logging.getLogger(__name__)

order_contact_router = Router()


class AdminContactStates(StatesGroup):
    waiting_for_message = State()


@order_contact_router.callback_query(F.data.startswith("admin_order_contact_client:"))
async def process_contact_client_start(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    state: FSMContext,
):
    """
    Запрос у администратора текста для отправки клиенту.
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

    # Сохраняем необходимые данные и message_id карточки в стейт
    await state.set_state(AdminContactStates.waiting_for_message)
    await state.update_data(
        target_user_id=order.user.id,
        order_id=order_id,
        status=status,
        page=page,
        card_message_id=callback.message.message_id,
    )

    # Кнопка отмены, чтобы админ мог выйти из режима ввода текста
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_order_view:{order_id}:{status}:{page}")]
        ]
    )

    await callback.message.edit_text(
        text=f"💬 <b>Связь с клиентом (Заказ #{order_id})</b>\n\n"
             f"Введите текст сообщения, который хотите отправить покупателю:",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@order_contact_router.message(AdminContactStates.waiting_for_message)
async def process_send_client_message(
    message: Message,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
):
    """
    Получает текст от администратора, отправляет сообщение клиенту,
    удаляет сообщение с введенным текстом, а затем возвращает карточку заказа.
    """
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    order_id = data.get("order_id")
    status = data.get("status", "all")
    page = data.get("page", 1)
    card_message_id = data.get("card_message_id")

    await state.clear()

    # Удаляем сообщение с введенным текстом от администратора, чтобы не засорять чат
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"[ADMIN CONTACT] Could not delete admin message: {e}")

    if not target_user_id or not order_id:
        return

    # Временная клавиатура "Ответить" для клиента
    client_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить администратору", callback_data=f"client_reply_order:{order_id}")]
        ]
    )

    try:
        # Отправляем сообщение клиенту от имени бота
        await message.bot.send_message(
            chat_id=target_user_id,
            text=f"💬 <b>Сообщение от администрации по заказу #{order_id}:</b>\n\n{message.text}",
            reply_markup=client_kb,
        )
    except Exception as e:
        logger.error(f"[ADMIN CONTACT] Failed to send message to user {target_user_id}: {e}")
        # Если не удалось отправить, можем показать алерт через отправку временного сообщения или лог
        return

    # Перерисовываем исходное сообщение с карточкой заказа наверх с помощью message_id_to_edit
    await render_order_detail(
        event=message,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
        message_id_to_edit=card_message_id,
    )