"""Глобальный обработчик ошибок бота.

Ловит любые необработанные исключения из хэндлеров, логирует их с полным
traceback и показывает пользователю вежливое локализованное сообщение.
Безобидные ошибки Telegram API (например, "message is not modified")
пользователю не показываются — только логируются.
"""
from aiogram import Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ErrorEvent

from shopcrm_core.logging import logger
from shopcrm_bot.locales import Locale

# Подстроки в message у TelegramAPIError, которые считаются безобидными
# и не должны беспокоить пользователя.
_BENIGN_API_ERROR_MARKERS = (
    "message is not modified",
    "query is too old and response text doesn't changed",
    "message to delete not found",
    "message id invalid",
    "query id invalid",
)

_FALLBACK_ERROR_TEXT = "⚠️ Something went wrong. Please try again."


def _is_benign_api_error(exc: BaseException) -> bool:
    """True, если это безобидная ошибка Telegram API (не показываем юзеру)."""
    if not isinstance(exc, TelegramAPIError):
        return False
    message = (exc.message or "").lower()
    return any(marker in message for marker in _BENIGN_API_ERROR_MARKERS)


def _resolve_error_text(user) -> str:
    """Локализованное сообщение об ошибке (best-effort, без исключений)."""
    try:
        lang = getattr(user, "language", None) or "en"
        return Locale(lang=lang).get_text("client.error_generic")
    except Exception:  # noqa: BLE001 — локализация не должна ронять обработчик
        return _FALLBACK_ERROR_TEXT


async def _notify_user(update, text: str) -> None:
    """Best-effort уведомление пользователя об ошибке (без исключений наружу)."""
    try:
        if isinstance(update, CallbackQuery):
            await update.bot.answer_callback_query(callback_query_id=update.id)
            target = update.message
        else:
            target = update  # Message / EditedMessage / ChannelPost имеют .reply()
        if target is not None and hasattr(target, "reply"):
            await target.reply(text)
    except Exception:  # noqa: BLE001 — сбой в уведомлении не должен ронять обработку
        logger.debug(
            f"Failed to send error notification for update id={getattr(update, 'update_id', '?')}"
        )


async def error_handler(event: ErrorEvent, **kwargs) -> None:
    """Глобальный обработчик ошибок: лог с traceback + вежливое сообщение юзеру."""
    update = event.update
    exception = event.exception

    logger.opt(exception=exception).error(
        f"Unhandled exception while processing update id={getattr(update, 'update_id', '?')}: "
        f"{type(exception).__name__}: {exception}"
    )

    if _is_benign_api_error(exception):
        logger.debug(f"Benign Telegram API error ignored: {exception}")
        return

    user = kwargs.get("user")
    await _notify_user(update, _resolve_error_text(user))


def register_error_handlers(dp: Dispatcher) -> None:
    """Регистрирует глобальный обработчик ошибок на Dispatcher."""
    dp.errors.register(error_handler)