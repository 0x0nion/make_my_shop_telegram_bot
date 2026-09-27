"""Тесты меню команд бота (services/commands_service.py).

Проверяют:
- ``/start`` видят все, ``/admin`` — только администраторы;
- описания команд локализованы;
- ``ensure_bot_commands`` ставит per-chat scope (BotCommandScopeChat);
- кэш предотвращает повторные API-вызовы, но реагирует на смену языка;
- ошибка API не прерывает обработку апдейта;
- middleware выставляет per-chat команды админам.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import BotCommandScopeChat, CallbackQuery, Chat, Message, User as TgUser

from shopcrm_bot.services import commands_service
from shopcrm_bot.services.commands_service import build_commands, ensure_bot_commands


@pytest.fixture(autouse=True)
def _clear_commands_cache():
    """Изоляция in-memory кэша между тестами."""
    commands_service._configured.clear()
    yield
    commands_service._configured.clear()


class TestBuildCommands:
    def test_non_admin_gets_start_only(self):
        """Не-админ: только /start."""
        cmds = build_commands(is_admin=False)
        assert [c.command for c in cmds] == ["start"]

    def test_admin_gets_start_and_admin(self):
        """Админ: /start + /admin."""
        cmds = build_commands(is_admin=True)
        assert [c.command for c in cmds] == ["start", "admin"]

    def test_descriptions_localized(self):
        """Описания команд берутся из локали."""
        ru = {c.command: c.description for c in build_commands(is_admin=True, lang="ru")}
        en = {c.command: c.description for c in build_commands(is_admin=True, lang="en")}
        assert ru["start"] == "Перезапустить меню"
        assert en["start"] == "Restart the menu"
        assert ru["admin"] == "Админ-панель"
        assert en["admin"] == "Admin panel"


class TestEnsureBotCommands:
    async def test_sets_per_chat_scope(self):
        """Команды ставятся в per-chat scope конкретного чата."""
        bot = AsyncMock()
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=True, lang="en")

        bot.set_my_commands.assert_awaited_once()
        _, kwargs = bot.set_my_commands.await_args
        assert isinstance(kwargs["scope"], BotCommandScopeChat)
        assert kwargs["scope"].chat_id == 1

    async def test_cached_no_repeat_calls(self):
        """Повторный вызов для того же (чат, роль, язык) — без API-вызова."""
        bot = AsyncMock()
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=True, lang="en")
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=True, lang="en")
        assert bot.set_my_commands.await_count == 1

    async def test_language_change_triggers_update(self):
        """Смена языка админа — команды переставляются с новым описанием."""
        bot = AsyncMock()
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=True, lang="en")
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=True, lang="ru")
        assert bot.set_my_commands.await_count == 2

    async def test_admin_status_change_triggers_update(self):
        """Смена прав (админ → не-админ) — команды переставляются."""
        bot = AsyncMock()
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=True, lang="en")
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=False, lang="en")
        assert bot.set_my_commands.await_count == 2

    async def test_api_error_does_not_raise(self):
        """Ошибка API логируется, не падает; при следующем вызове — повтор."""
        bot = AsyncMock()
        bot.set_my_commands = AsyncMock(side_effect=RuntimeError("api down"))
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=False, lang="en")

        bot.set_my_commands = AsyncMock()
        await ensure_bot_commands(bot=bot, chat_id=1, is_admin=False, lang="en")
        assert bot.set_my_commands.await_count == 1


class TestMiddlewareSetsCommands:
    """DbSessionMiddleware выставляет per-chat команды для администраторов."""

    def _make_message(self, user_id: int) -> Message:
        return Message(
            message_id=1,
            date=datetime(2026, 1, 1),
            chat=Chat(id=user_id, type="private"),
            from_user=TgUser(id=user_id, is_bot=False, first_name="Test"),
            text="/start",
        )

    def _make_middleware(self, monkeypatch, db_user: SimpleNamespace):
        """Middleware с замещёнными репозиториями и ensure_bot_commands."""
        import shopcrm_bot.middlewares.db as db_mw

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        pool = MagicMock(return_value=session)

        user_repo = AsyncMock()
        user_repo.get_or_create_user = AsyncMock(return_value=db_user)

        monkeypatch.setattr(db_mw, "UserRepository", lambda s: user_repo)
        monkeypatch.setattr(db_mw, "AdminRepository", lambda s: AsyncMock())
        monkeypatch.setattr(db_mw, "ShopRepository", lambda s: AsyncMock())
        monkeypatch.setattr(db_mw, "AdminShopService", lambda r: AsyncMock())

        ensure_mock = AsyncMock()
        monkeypatch.setattr(db_mw, "ensure_bot_commands", ensure_mock)

        from shopcrm_bot.middlewares.db import DbSessionMiddleware

        return DbSessionMiddleware(session_pool=pool), ensure_mock

    async def test_admin_gets_per_chat_commands(self, monkeypatch):
        """Админ (id из config.ADMIN_ID) — команды с /admin."""
        from shopcrm_bot.config import config

        admin_id = config.ADMIN_ID[0]
        mw, ensure_mock = self._make_middleware(
            monkeypatch, SimpleNamespace(id=admin_id, language="ru")
        )

        async def handler(event, data):
            return "ok"

        result = await mw(handler, self._make_message(admin_id), {"bot": AsyncMock()})

        assert result == "ok"
        ensure_mock.assert_awaited_once()
        kwargs = ensure_mock.await_args.kwargs
        assert kwargs["chat_id"] == admin_id
        assert kwargs["is_admin"] is True
        assert kwargs["lang"] == "ru"

    async def test_non_admin_gets_start_only(self, monkeypatch):
        """Не-админ — команды без /admin."""
        from shopcrm_bot.config import config

        non_admin_id = max(config.ADMIN_ID) + 1
        mw, ensure_mock = self._make_middleware(
            monkeypatch, SimpleNamespace(id=non_admin_id, language="en")
        )

        async def handler(event, data):
            return "ok"

        await mw(handler, self._make_message(non_admin_id), {"bot": AsyncMock()})

        ensure_mock.assert_awaited_once()
        assert ensure_mock.await_args.kwargs["is_admin"] is False

    def _make_callback_query(self, user_id: int, chat_id: int) -> CallbackQuery:
        """CallbackQuery с сообщением в чате, id которого != id пользователя."""
        return CallbackQuery(
            id="cb1",
            from_user=TgUser(id=user_id, is_bot=False, first_name="Test"),
            chat_instance="ci1",
            message=self._make_message(chat_id),
            data="test",
        )

    async def test_callback_query_uses_message_chat(self, monkeypatch):
        """Регрессия: у CallbackQuery нет .chat — берём message.chat.id."""
        from shopcrm_bot.config import config

        admin_id = config.ADMIN_ID[0]
        chat_id = admin_id + 1000  # chat_id != user_id, чтобы не спутать
        mw, ensure_mock = self._make_middleware(
            monkeypatch, SimpleNamespace(id=admin_id, language="ru")
        )

        async def handler(event, data):
            return "ok"

        result = await mw(
            handler, self._make_callback_query(admin_id, chat_id), {"bot": AsyncMock()}
        )

        assert result == "ok"
        ensure_mock.assert_awaited_once()
        kwargs = ensure_mock.await_args.kwargs
        assert kwargs["chat_id"] == chat_id
        assert kwargs["is_admin"] is True

    async def test_callback_query_without_message_does_not_crash(self, monkeypatch):
        """CallbackQuery с message=None (удалённое сообщение) — без падения."""
        from shopcrm_bot.config import config

        admin_id = config.ADMIN_ID[0]
        mw, ensure_mock = self._make_middleware(
            monkeypatch, SimpleNamespace(id=admin_id, language="ru")
        )

        async def handler(event, data):
            return "ok"

        cq = CallbackQuery(
            id="cb2",
            from_user=TgUser(id=admin_id, is_bot=False, first_name="Test"),
            chat_instance="ci2",
        )
        result = await mw(handler, cq, {"bot": AsyncMock()})

        assert result == "ok"
        ensure_mock.assert_not_awaited()
