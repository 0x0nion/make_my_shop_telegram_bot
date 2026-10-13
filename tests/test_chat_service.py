"""Тесты сервиса форматирования переписки по заказу (format_chat_history).

Проверяют:
- пустую историю (без кнопок пагинации);
- одну страницу (кнопок нет);
- пагинацию: кнопки с правильным callback-префиксом (admin/client);
- клампинг страницы за пределами диапазона.
"""
from shopcrm_bot.locales import Locale
from shopcrm_bot.services.chat_service import MESSAGES_PER_PAGE, format_chat_history


def _history(n: int) -> list[dict]:
    """Фабрика: n сообщений с чередованием admin/client."""
    return [
        {
            "sender": "admin" if i % 2 == 0 else "client",
            "text": f"msg-{i}",
            "time": f"t{i}",
        }
        for i in range(n)
    ]


class TestFormatChatHistory:
    def test_empty_history(self):
        """Пустая история: текст-заглушка, кнопок нет."""
        locale = Locale("ru")
        text, buttons = format_chat_history(None, locale)
        assert "История переписки пуста" in text
        assert buttons is None

    def test_single_page_no_buttons(self):
        """Одна страница: все сообщения в тексте, кнопок пагинации нет."""
        locale = Locale("ru")
        text, buttons = format_chat_history(_history(MESSAGES_PER_PAGE), locale)
        assert "msg-0" in text
        assert "msg-4" in text
        assert "Страница 1 из 1" in text
        assert buttons is None

    def test_first_page_forward_button_with_prefix(self):
        """Первая из двух страниц: только кнопка вперёд с нужным префиксом."""
        locale = Locale("ru")
        text, buttons = format_chat_history(
            _history(MESSAGES_PER_PAGE + 1),
            locale,
            page=1,
            callback_prefix="client_chat_page",
        )
        assert "msg-0" in text
        assert "msg-5" not in text
        assert "Страница 1 из 2" in text
        assert buttons is not None
        assert [b.callback_data for b in buttons] == ["client_chat_page:2"]

    def test_last_page_back_button_with_prefix(self):
        """Последняя страница: только кнопка назад с нужным префиксом."""
        locale = Locale("ru")
        text, buttons = format_chat_history(
            _history(MESSAGES_PER_PAGE + 1),
            locale,
            page=2,
            callback_prefix="client_chat_page",
        )
        assert "msg-5" in text
        assert "msg-0" not in text
        assert "Страница 2 из 2" in text
        assert [b.callback_data for b in buttons] == ["client_chat_page:1"]

    def test_default_prefix_is_admin(self):
        """По умолчанию префикс админский (admin_chat_page)."""
        locale = Locale("ru")
        _, buttons = format_chat_history(_history(MESSAGES_PER_PAGE + 1), locale, page=1)
        assert [b.callback_data for b in buttons] == ["admin_chat_page:2"]

    def test_page_clamped_to_range(self):
        """Страница за пределами диапазона ограничивается допустимой."""
        locale = Locale("ru")
        text, _ = format_chat_history(_history(2), locale, page=99)
        assert "Страница 1 из 1" in text
