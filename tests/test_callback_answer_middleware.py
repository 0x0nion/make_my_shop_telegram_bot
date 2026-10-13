"""Тесты CallbackAnswerMiddleware (авто-ответ на callback_query).

Проверяют:
- мидлварь отвечает на callback, если хэндлер этого не сделал;
- мидлварь не падает, если хэндлер уже ответил (alert/текст) —
  повторный ответ Telegram отклоняет («query id invalid»);
- результат хэндлера возвращается без изменений.
"""
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramBadRequest

from shopcrm_bot.middlewares.callback_answer import CallbackAnswerMiddleware


def _query_id_invalid() -> TelegramBadRequest:
    """Фабрика «query id invalid» (повторный ответ на callback)."""
    return TelegramBadRequest(method=MagicMock(), message="query id invalid")


class TestCallbackAnswerMiddleware:
    async def test_answers_when_handler_did_not(self):
        """Хэндлер молчит → мидлварь отвечает на callback."""
        mw = CallbackAnswerMiddleware()
        callback = AsyncMock()

        async def handler(event, data):
            return "ok"

        result = await mw(handler, callback, {})
        assert result == "ok"
        callback.answer.assert_awaited_once()

    async def test_ignores_already_answered(self):
        """Хэндлер уже ответил → повторный ответ мидлваря игнорируется."""
        mw = CallbackAnswerMiddleware()
        callback = AsyncMock()
        # 1-й ответ (хэндлер) — ок, 2-й (мидлварь) — «query id invalid».
        callback.answer = AsyncMock(
            side_effect=[None, _query_id_invalid()]
        )

        async def handler(event, data):
            await event.answer()
            return "ok"

        result = await mw(handler, callback, {})
        assert result == "ok"
        assert callback.answer.await_count == 2

    async def test_returns_handler_result(self):
        """Мидлварь не меняет результат хэндлера."""
        mw = CallbackAnswerMiddleware()
        callback = AsyncMock()

        async def handler(event, data):
            return {"status": "done"}

        result = await mw(handler, callback, {})
        assert result == {"status": "done"}
