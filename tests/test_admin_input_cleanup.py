"""Тесты «одного сообщения»: ввод админа удаляется в ветках ошибок.

Покрыто:
- catalog: неверное название категории → ввод админа удалён до показа ошибки;
- welcome_editor: слишком длинный текст приветствия → ввод удалён;
- welcome_editor: прислан не фото → неверный ввод удалён;
- contact: не-текстовое сообщение админа (фото/стикер) → ввод удалён до гварда.
"""
from unittest.mock import AsyncMock, patch

from shopcrm_bot.handlers.admin.orders import contact as contact_module
from shopcrm_bot.handlers.admin.orders.contact import process_send_client_message
from shopcrm_bot.handlers.admin.shop import catalog as catalog_module
from shopcrm_bot.handlers.admin.shop import welcome_editor as welcome_module
from shopcrm_bot.handlers.admin.shop.catalog import process_add_category
from shopcrm_bot.handlers.admin.shop.welcome_editor import (
    process_welcome_photo_invalid,
    process_welcome_text_input,
)
from shopcrm_bot.locales import Locale


def _message(text: str | None) -> AsyncMock:
    """Фабрика мок-Message с заданным текстом (None = не-текст)."""
    msg = AsyncMock()
    msg.text = text
    msg.from_user.id = 1
    return msg


def _state(data: dict | None = None) -> AsyncMock:
    st = AsyncMock()
    st.get_data.return_value = data or {}
    return st


def _user(lang: str = "ru") -> AsyncMock:
    u = AsyncMock()
    u.language = lang
    return u


class TestAddCategoryInputCleanup:
    """catalog.process_add_category: удаление ввода при ошибке валидации."""

    async def test_invalid_name_deletes_input(self):
        message = _message("x" * 40)  # > NAME_MAX_LENGTH (30)
        state = _state({"parent_id": None, "menu_message_id": None})
        admin_repo = AsyncMock()
        user = _user("ru")

        with patch.object(catalog_module, "self_destruct", AsyncMock()) as mock_sd:
            await process_add_category(message, state, admin_repo, Locale("ru"), user)

        # Ввод админа удалён ДО показа ошибки
        message.delete.assert_awaited_once()
        message.answer.assert_awaited_once()
        # Категория не создана, self_destruct запланирован для сообщения об ошибке
        admin_repo.create_category.assert_not_awaited()
        mock_sd.assert_called_once()


class TestWelcomeTextInputCleanup:
    """welcome_editor.process_welcome_text_input: удаление ввода при ошибке."""

    async def test_too_long_text_deletes_input(self):
        message = _message("x" * 600)  # > DESCRIPTION_MAX_LENGTH (500)
        state = _state({"menu_message_id": 10})
        admin_repo = AsyncMock()
        user = _user("ru")

        with patch.object(welcome_module, "self_destruct", AsyncMock()) as mock_sd:
            await process_welcome_text_input(message, state, admin_repo, user)

        message.delete.assert_awaited_once()
        message.answer.assert_awaited_once()
        mock_sd.assert_called_once()


class TestWelcomePhotoInvalidCleanup:
    """welcome_editor.process_welcome_photo_invalid: удаление неверного ввода."""

    async def test_non_photo_deletes_input(self):
        message = _message(None)  # не фото
        user = _user("ru")

        with patch.object(welcome_module, "self_destruct", AsyncMock()) as mock_sd:
            await process_welcome_photo_invalid(message, user)

        message.delete.assert_awaited_once()
        message.answer.assert_awaited_once()
        mock_sd.assert_called_once()


class TestContactNonTextInputCleanup:
    """contact.process_send_client_message: удаление не-текста до гварда."""

    async def test_non_text_admin_message_deleted(self):
        message = _message(None)  # фото/стикер/голосовое
        state = _state(
            {
                "target_user_id": 100,
                "order_id": 7,
                "status": "all",
                "page": 1,
                "card_message_id": 55,
                "client_language": "ru",
            }
        )
        admin_repo = AsyncMock()
        user = _user("ru")

        with patch.object(contact_module.UIManager, "show", AsyncMock()) as mock_show:
            await process_send_client_message(message, state, admin_repo, user)

        # Ввод админа удалён ДО проверки текста
        message.delete.assert_awaited_once()
        state.clear.assert_awaited_once()
        # Показана подсказка «только текст», сообщение не сохранено
        mock_show.assert_awaited_once()
        admin_repo.append_order_chat_history.assert_not_awaited()
