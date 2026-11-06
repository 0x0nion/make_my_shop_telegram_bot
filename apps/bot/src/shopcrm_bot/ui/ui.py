
import contextlib

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message
from shopcrm_core.logging import logger


class UIManager:
    @staticmethod
    def _extract_bot_and_chat(
        bot: Bot | None,
        chat_id: int | None,
        event: Message | CallbackQuery | None
    ) -> tuple[Bot, int]:
        """Извлекает bot и chat_id из переданных аргументов или объекта события."""
        if bot and chat_id:
            return bot, chat_id

        if isinstance(event, Message):
            return event.bot, event.chat.id
        elif isinstance(event, CallbackQuery):
            return event.bot, event.message.chat.id

        raise ValueError("UIManager requires either (bot + chat_id) or a valid aiogram event (Message/CallbackQuery).")

    @classmethod
    async def show(
        cls,
        text: str,
        bot: Bot | None = None,
        chat_id: int | None = None,
        event: Message | CallbackQuery | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        photo: str | None = None,
        message_id_to_edit: int | None = None,
    ) -> Message | None:
        """
        Единый метод отрисовки UI.
        Гарантирует отображение контекста строго в 1 сообщении.
        """
        bot, chat_id = cls._extract_bot_and_chat(bot, chat_id, event)

        # Если message_id_to_edit не передан явно, но передан CallbackQuery — берём ID из него
        if not message_id_to_edit and isinstance(event, CallbackQuery) and event.message:
            message_id_to_edit = event.message.message_id

        # 1. Попытка редактирования
        if message_id_to_edit:
            try:
                if photo:
                    return await bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id_to_edit,
                        media=InputMediaPhoto(media=photo, caption=text, parse_mode="HTML"),
                        reply_markup=reply_markup,
                    )
                else:
                    return await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id_to_edit,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )
            except TelegramBadRequest as e:
                err_msg = str(e).lower()

                # Если контент идентичен — просто игнорируем
                if "message is not modified" in err_msg:
                    logger.debug(f"[UI] Message {message_id_to_edit} not modified.")
                    return None

                # Во всех остальных случаях (сменился тип фото/текст, сообщение слишком старо и т.д.):
                # Удаляем старое сообщение, чтобы на его месте отправить новое и сохранить правило 1 сообщения!
                logger.info(
                    f"[UI] Cannot edit message {message_id_to_edit} ({e}). Re-creating UI frame."
                )
                # Если сообщение уже удалено пользователем — просто отправляем новое
                with contextlib.suppress(TelegramBadRequest):
                    await bot.delete_message(chat_id=chat_id, message_id=message_id_to_edit)

        # 2. Отправка нового сообщения (если редактирование не требовалось или не удалось)
        if photo:
            try:
                return await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                )
            except TelegramBadRequest as e:
                # Фото недоступно (например, file ID принадлежит другому боту) —
                # отправляем то же сообщение без фото, чтобы UI не «пропал».
                logger.warning(f"[UI] Cannot send photo ({e}). Falling back to text message.")

        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )