"""Тесты фолбэка на текстовое сообщение при недоступном фото.

Сценарий: file ID фото принадлежит другому боту (например, после смены токена
в self-hosted окружении) — Telegram отвечает TelegramBadRequest
«wrong file identifier». UI не должен «пропадать»: вместо фото отправляется
то же текстовое сообщение.

Покрыто:
- UIManager.show: сбой отправки фото → текстовый фолбэк;
- UIManager.show: edit-путь (старое сообщение удалено, новое отправлено текстом);
- UIManager.show: «message is not modified» → действий нет;
- notify_admins_about_payment: сбой фото чека → текстовое уведомление.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest

from shopcrm_bot.services.notification_service import notify_admins_about_payment
from shopcrm_bot.ui import UIManager
from shopcrm_core.constants import PaymentProofType

WRONG_FILE_ID = TelegramBadRequest(
    method="sendPhoto",
    message="Bad Request: wrong file identifier/HTTP URL specified",
)


def _make_bot() -> AsyncMock:
    """Мок-бот, у которого все методы возвращают различимые сообщения."""
    bot = AsyncMock()
    bot.send_photo.return_value = SimpleNamespace(kind="photo")
    bot.send_message.return_value = SimpleNamespace(kind="text")
    bot.edit_message_media.return_value = SimpleNamespace(kind="edited_media")
    bot.edit_message_text.return_value = SimpleNamespace(kind="edited_text")
    bot.delete_message.return_value = True
    return bot


class TestShowPhotoFallback:
    """UIManager.show: отправка нового сообщения с фото."""

    async def test_photo_sent_successfully(self):
        bot = _make_bot()
        result = await UIManager.show(bot=bot, chat_id=1, text="Card", photo="file_id")
        bot.send_photo.assert_awaited_once()
        bot.send_message.assert_not_awaited()
        assert result is bot.send_photo.return_value

    async def test_photo_fails_falls_back_to_text(self):
        bot = _make_bot()
        bot.send_photo.side_effect = WRONG_FILE_ID
        result = await UIManager.show(bot=bot, chat_id=1, text="Card", photo="file_id")
        bot.send_photo.assert_awaited_once()
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.kwargs["text"] == "Card"
        assert result is bot.send_message.return_value


class TestShowEditPath:
    """UIManager.show: редактирование старого сообщения с фото."""

    async def test_edit_and_photo_fail_falls_back_to_text(self):
        bot = _make_bot()
        bot.edit_message_media.side_effect = WRONG_FILE_ID
        bot.send_photo.side_effect = WRONG_FILE_ID
        result = await UIManager.show(
            bot=bot, chat_id=1, text="Card", photo="file_id", message_id_to_edit=42
        )
        bot.delete_message.assert_awaited_once_with(chat_id=1, message_id=42)
        bot.send_message.assert_awaited_once()
        assert result is bot.send_message.return_value

    async def test_edit_fails_photo_ok_sends_photo(self):
        bot = _make_bot()
        bot.edit_message_media.side_effect = TelegramBadRequest(
            method="editMessageMedia", message="Bad Request: message can't be edited"
        )
        result = await UIManager.show(
            bot=bot, chat_id=1, text="Card", photo="file_id", message_id_to_edit=42
        )
        bot.delete_message.assert_awaited_once_with(chat_id=1, message_id=42)
        bot.send_photo.assert_awaited_once()
        bot.send_message.assert_not_awaited()
        assert result is bot.send_photo.return_value

    async def test_message_not_modified_no_action(self):
        bot = _make_bot()
        bot.edit_message_media.side_effect = TelegramBadRequest(
            method="editMessageMedia", message="Bad Request: message is not modified"
        )
        result = await UIManager.show(
            bot=bot, chat_id=1, text="Card", photo="file_id", message_id_to_edit=42
        )
        assert result is None
        bot.delete_message.assert_not_awaited()
        bot.send_photo.assert_not_awaited()
        bot.send_message.assert_not_awaited()


class TestShowTextOnly:
    """UIManager.show: сообщение без фото."""

    async def test_no_photo_sends_text(self):
        bot = _make_bot()
        result = await UIManager.show(bot=bot, chat_id=1, text="Card")
        bot.send_photo.assert_not_awaited()
        bot.send_message.assert_awaited_once()
        assert result is bot.send_message.return_value


class TestPaymentProofPhotoFallback:
    """notify_admins_about_payment: фото чека об оплате недоступно."""

    def _order(self) -> SimpleNamespace:
        return SimpleNamespace(
            id=42,
            payment_proof_type=PaymentProofType.PHOTO.value,
            payment_proof="proof_file_id",
        )

    def _repos(self):
        user_repo = AsyncMock()
        user_repo.get_user = AsyncMock(return_value=SimpleNamespace(id=7, language="en"))
        return AsyncMock(), user_repo

    async def test_proof_photo_fails_falls_back_to_text(self):
        bot = _make_bot()
        bot.send_photo.side_effect = WRONG_FILE_ID
        admin_repo, user_repo = self._repos()
        with patch(
            "shopcrm_bot.services.notification_service.build_order_detail_text",
            new=AsyncMock(return_value=("Order text", self._order())),
        ):
            await notify_admins_about_payment(
                bot=bot,
                admin_repo=admin_repo,
                user_repo=user_repo,
                order_id=42,
                admin_ids=[7],
            )
        bot.send_photo.assert_awaited_once()
        bot.send_message.assert_awaited_once()
        assert "Order text" in bot.send_message.await_args.kwargs["text"]

    async def test_proof_photo_ok_no_text_fallback(self):
        bot = _make_bot()
        admin_repo, user_repo = self._repos()
        with patch(
            "shopcrm_bot.services.notification_service.build_order_detail_text",
            new=AsyncMock(return_value=("Order text", self._order())),
        ):
            await notify_admins_about_payment(
                bot=bot,
                admin_repo=admin_repo,
                user_repo=user_repo,
                order_id=42,
                admin_ids=[7],
            )
        bot.send_photo.assert_awaited_once()
        bot.send_message.assert_not_awaited()

