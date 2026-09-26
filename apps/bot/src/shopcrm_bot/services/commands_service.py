# services/commands_service.py
"""Регистрация команд бота (меню при вводе «/»).

- ``/start`` — видят все, перезапускает меню.
- ``/admin`` — видят только администраторы (per-chat scope).

Глобальный scope (только ``/start``) выставляется при старте бота (``main.py``);
для администраторов ``ensure_bot_commands`` переопределяет команды в их чате.
"""
import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from shopcrm_bot.locales import Locale

logger = logging.getLogger(__name__)

# In-memory кэш уже настроенных чатов: (chat_id, is_admin, lang).
# Позволяет не дёргать set_my_commands на каждый апдейт и корректно
# переставлять команды при смене языка или изменении прав админа.
_configured: set[tuple[int, bool, str]] = set()


def build_commands(is_admin: bool, lang: str = "en") -> list[BotCommand]:
    """Собирает список команд: ``/start`` для всех, ``/admin`` — только админам."""
    locale = Locale(lang)
    commands = [
        BotCommand(command="start", description=locale.get_text("base.cmd_start_desc")),
    ]
    if is_admin:
        commands.append(
            BotCommand(command="admin", description=locale.get_text("base.cmd_admin_desc"))
        )
    return commands


async def ensure_bot_commands(
    bot: Bot,
    chat_id: int,
    is_admin: bool,
    lang: str = "en",
) -> None:
    """Выставляет per-chat команды для чата (идемпотентно, с кэшированием).

    Ошибки API не прерывают обработку апдейта — только логируются.
    """
    key = (chat_id, is_admin, lang)
    if key in _configured:
        return
    try:
        await bot.set_my_commands(
            build_commands(is_admin=is_admin, lang=lang),
            scope=BotCommandScopeChat(chat_id=chat_id),
        )
        _configured.add(key)
    except Exception as e:
        logger.warning(f"Не удалось установить команды для чата {chat_id}: {e}")
