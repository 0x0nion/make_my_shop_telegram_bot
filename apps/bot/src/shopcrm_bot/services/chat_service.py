# services/chat_service.py
"""Общие функции форматирования переписки по заказу (admin/client).

История переписки хранится в ``Order.chat_history`` (JSON-список записей
``{"sender": "admin"|"client", "text": str, "time": str}``). Функция
:func:`format_chat_history` рендерит её с пагинацией и возвращает текст
вместе с кнопками навигации. Используется и админским, и клиентским
хэндлерами — поэтому префикс callback-данных пагинации параметризован.
"""
from aiogram.types import InlineKeyboardButton

from shopcrm_bot.locales import Locale

# Количество сообщений на одной странице пагинации чата
MESSAGES_PER_PAGE = 5


def format_chat_history(
    chat_history: list | None,
    locale: Locale,
    page: int = 1,
    callback_prefix: str = "admin_chat_page",
) -> tuple[str, list[InlineKeyboardButton] | None]:
    """Форматирует историю переписки для отображения с пагинацией.

    :param chat_history: список записей переписки (или ``None``/пустой список).
    :param locale: локаль для текстов.
    :param page: текущая страница (1-based), при выходе за пределы —
        ограничивается допустимым диапазоном.
    :param callback_prefix: префикс callback-данных кнопок пагинации
        (``admin_chat_page`` для админа, ``client_chat_page`` для клиента).
    :return: кортеж ``(history_text, pagination_buttons)``; кнопки — ``None``,
        если пагинация не нужна (одна страница или пустой чат).
    """
    if not chat_history:
        return locale.get_text("admin.orders.chat_empty") + "\n\n", None

    total_messages = len(chat_history)
    total_pages = max(1, (total_messages + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE)
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * MESSAGES_PER_PAGE
    end_idx = start_idx + MESSAGES_PER_PAGE
    page_messages = chat_history[start_idx:end_idx]

    history_text = locale.get_text("admin.orders.chat_title") + "\n" + "—" * 20 + "\n"

    for msg in page_messages:
        sender = msg.get("sender")
        text = msg.get("text", "")
        time_str = msg.get("time", "")

        if sender == "admin":
            author = locale.get_text("admin.orders.author_admin")
        else:
            author = locale.get_text("admin.orders.author_client")

        history_text += f"{author} <i>({time_str})</i>:\n{text}\n\n"

    history_text += (
        "—" * 20 + "\n"
        + locale.get_text("admin.orders.chat_page", page=current_page, total=total_pages)
        + "\n\n"
    )

    pagination_buttons: list[InlineKeyboardButton] | None = None
    if total_pages > 1:
        pagination_buttons = []
        if current_page > 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text=locale.get_text("base.back"),
                    callback_data=f"{callback_prefix}:{current_page - 1}",
                )
            )
        if current_page < total_pages:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text=locale.get_text("base.forward"),
                    callback_data=f"{callback_prefix}:{current_page + 1}",
                )
            )

    return history_text, pagination_buttons
