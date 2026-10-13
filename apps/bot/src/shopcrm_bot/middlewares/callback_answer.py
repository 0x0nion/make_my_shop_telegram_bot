"""Мидлварь авто-ответа на callback_query.

Убирает «часики» (спиннер) на кнопках inline-клавиатуры: часть хэндлеров
не вызывает ``callback.answer()``, из-за чего спиннер висит до таймаута
Telegram. Мидлварь отвечает на callback после выполнения хэндлера, но только
если хэндлер ещё не ответил.

Почему «после», а не «до» хэндлера:
- Telegram позволяет ответить на callback только один раз.
- Многие хэндлеры отвечают с ``show_alert=True`` (ошибки, подтверждения).
  Если мидлварь ответит «до», эти алерты перестанут работать.
- «После» безопасно: ответ хэндлера имеет приоритет, а повторный ответ
  мидлваря отклоняется Telegram («query id invalid») и молча игнорируется.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from shopcrm_core.logging import logger


class CallbackAnswerMiddleware(BaseMiddleware):
    """Автоматически отвечает на callback_query, если хэндлер этого не сделал."""

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        await self._safe_answer(event)
        return result

    @staticmethod
    async def _safe_answer(callback: CallbackQuery) -> None:
        """Ответить на callback, игнорируя «уже отвечено» / «слишком старый»."""
        try:
            await callback.answer()
        except TelegramBadRequest as exc:
            # Хэндлер уже ответил (alert/текст) или callback устарел —
            # повторный ответ не нужен.
            logger.debug(f"Callback auto-answer skipped: {exc}")
