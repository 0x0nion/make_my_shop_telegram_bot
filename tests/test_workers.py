"""Тесты раздела «Работники»: сервис, хэндлеры, FSM, клавиатуры, middleware."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from shopcrm_bot.handlers.admin.workers.workers import (
    handle_worker_add_id,
    handle_worker_add_position,
    route_worker_add,
    route_worker_delete,
    route_worker_delete_confirm,
    route_workers_main_menu,
    route_workers_page,
)
from shopcrm_bot.locales import Locale
from shopcrm_bot.states.admin_states import AdminWorkerState
from shopcrm_bot.ui.presenters.workers import PAGE_SIZE, WorkersUI
from shopcrm_core.services.admin_worker_service import WorkerEntry

# ==================== Мок-хелперы ====================

def _callback(data: str = "admin_workers") -> AsyncMock:
    cb = AsyncMock()
    cb.data = data
    cb.from_user = SimpleNamespace(id=1, language="ru")
    cb.message.message_id = 42
    cb.message.answer = AsyncMock(return_value=AsyncMock())
    return cb


def _message(text: str) -> AsyncMock:
    msg = AsyncMock()
    msg.text = text
    msg.chat = SimpleNamespace(id=1)
    msg.bot = AsyncMock()
    msg.delete = AsyncMock()
    msg.answer = AsyncMock(return_value=AsyncMock())
    return msg


def _fsm_state(data: dict | None = None) -> AsyncMock:
    st = AsyncMock()
    st.get_data = AsyncMock(return_value=data or {})
    st.clear = AsyncMock()
    st.set_state = AsyncMock()
    st.update_data = AsyncMock()
    return st


def _entry(telegram_id: int, position: str = "Менеджер", is_main: bool = False):
    return WorkerEntry(telegram_id=telegram_id, position=position, is_main=is_main)


def _kb_callbacks(markup) -> list[str]:
    """Все callback_data клавиатуры в порядке строк."""
    return [
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
    ]


# ==================== Сервис (реальная in-memory БД) ====================

class TestAdminWorkerService:
    def _service(self, session):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository
        from shopcrm_core.services.admin_worker_service import AdminWorkerService

        return AdminWorkerService(AdminRepository(session))

    async def test_list_workers_includes_main_admin(self, session):
        service = self._service(session)
        entries = await service.list_workers([10])
        assert entries == [
            WorkerEntry(telegram_id=10, position="", is_main=True)
        ]

    async def test_add_worker_success(self, session):
        service = self._service(session)
        worker, error = await service.add_worker(100, "Менеджер", [10])
        assert error is None
        assert worker.telegram_id == 100
        assert worker.position == "Менеджер"

        entries = await service.list_workers([10])
        assert [e.telegram_id for e in entries] == [10, 100]
        assert entries[1].is_main is False

    async def test_add_worker_duplicate(self, session):
        service = self._service(session)
        await service.add_worker(100, "Менеджер", [10])
        worker, error = await service.add_worker(100, "Курьер", [10])
        assert worker is None
        assert error == "already_admin"

    async def test_add_worker_main_admin_forbidden(self, session):
        service = self._service(session)
        worker, error = await service.add_worker(10, "Менеджер", [10])
        assert worker is None
        assert error == "already_admin"

    async def test_add_worker_empty_position(self, session):
        service = self._service(session)
        worker, error = await service.add_worker(100, "   ", [10])
        assert worker is None
        assert error == "invalid_position"

    async def test_remove_worker_success(self, session):
        service = self._service(session)
        await service.add_worker(100, "Менеджер", [10])
        removed, error = await service.remove_worker(100, [10])
        assert removed is True
        assert error is None
        assert await service.list_workers([10]) == [
            WorkerEntry(telegram_id=10, position="", is_main=True)
        ]

    async def test_remove_worker_main_admin_forbidden(self, session):
        """Главный админ из env не удаляется даже при поддельном callback."""
        service = self._service(session)
        removed, error = await service.remove_worker(10, [10])
        assert removed is False
        assert error == "main_admin"

    async def test_remove_worker_not_found(self, session):
        service = self._service(session)
        removed, error = await service.remove_worker(999, [10])
        assert removed is False
        assert error == "not_found"

    async def test_get_admin_ids_merges_and_dedupes(self, session):
        service = self._service(session)
        await service.add_worker(100, "Менеджер", [10])
        await service.add_worker(200, "Курьер", [10])
        # Дубль: 100 уже в main_admin_ids
        assert await service.get_admin_ids([10, 100]) == [10, 100, 200]

    async def test_db_worker_not_main_and_no_duplicate(self, session):
        """Регрессия: работник из БД не «главный», не дублируется, удаляется.

        Сценарий бага: хэндлер передавал в main_admin_ids объединённый
        список (env + БД) → новый работник рисовался дважды:
        «Main administrator» (виртуальная запись) + обычная запись из БД,
        и его нельзя было удалить.
        """
        service = self._service(session)
        await service.add_worker(100, "Менеджер", [10])

        # main_admin_ids — только env (как отдаёт middleware)
        entries = await service.list_workers([10])
        assert [e.telegram_id for e in entries] == [10, 100]
        assert [e.is_main for e in entries] == [True, False]
        # Без дублей
        ids = [e.telegram_id for e in entries]
        assert len(ids) == len(set(ids))

        # Работник из БД удаляется (не защищён как «главный»)
        removed, error = await service.remove_worker(100, [10])
        assert removed is True
        assert error is None

# ==================== Презентер: список ====================

class TestWorkersUIList:
    async def _show(self, entries, page=1, main_ids=(10,)):
        service = AsyncMock()
        service.list_workers = AsyncMock(return_value=entries)
        with patch("shopcrm_bot.ui.presenters.workers.UIManager") as ui:
            ui.show = AsyncMock()
            await WorkersUI.show_list(
                event=_callback(),
                service=service,
                main_admin_ids=list(main_ids),
                page=page,
                locale=Locale("ru"),
            )
        return ui.show

    async def test_list_renders_main_admin_and_workers(self):
        entries = [
            _entry(10, is_main=True),
            _entry(100, "Менеджер"),
        ]
        show = await self._show(entries)
        kwargs = show.call_args.kwargs
        assert "10" in kwargs["text"]
        assert "Главный администратор" in kwargs["text"]
        assert "100" in kwargs["text"]
        assert "Менеджер" in kwargs["text"]
        # Кнопка удаления только у работника, не у главного админа
        callbacks = _kb_callbacks(kwargs["reply_markup"])
        assert "admin_worker_del:100" in callbacks
        assert "admin_worker_del:10" not in callbacks
        assert "admin_worker_add" in callbacks
        assert "admin_main_menu" in callbacks

    async def test_list_empty(self):
        show = await self._show([])
        kwargs = show.call_args.kwargs
        assert "Работники не найдены" in kwargs["text"]
        # Без работников — без пагинации, но с кнопкой добавления
        callbacks = _kb_callbacks(kwargs["reply_markup"])
        assert "admin_worker_add" in callbacks
        assert "admin_workers_page:1" not in callbacks

    async def test_pagination_page_size(self):
        entries = [_entry(10, is_main=True)] + [
            _entry(100 + i, f"Позиция {i}") for i in range(6)
        ]  # 7 записей -> 2 страницы
        show = await self._show(entries, page=1)
        kwargs = show.call_args.kwargs
        # На первой странице ровно PAGE_SIZE записей
        assert kwargs["text"].count("ID: <code>") == PAGE_SIZE
        assert "104" not in kwargs["text"]  # 6-я запись — на 2-й странице
        callbacks = _kb_callbacks(kwargs["reply_markup"])
        # Круговая: с 1-й и «вперёд», и «назад» ведут на последнюю (2-ю)
        assert "admin_workers_page:2" in callbacks

        show2 = await self._show(entries, page=2)
        kwargs2 = show2.call_args.kwargs
        assert "105" in kwargs2["text"]
        assert "100" not in kwargs2["text"]
        callbacks2 = _kb_callbacks(kwargs2["reply_markup"])
        assert "admin_workers_page:1" in callbacks2  # круговая: с 2-й на 1-ю
        assert "admin_workers_page:3" not in callbacks2

    async def test_inplace_edit_id_passed(self):
        entries = [_entry(10, is_main=True)]
        with patch("shopcrm_bot.ui.presenters.workers.UIManager") as ui:
            ui.show = AsyncMock()
            await WorkersUI.show_list(
                event=_callback(),
                service=AsyncMock(list_workers=AsyncMock(return_value=entries)),
                main_admin_ids=[10],
                page=1,
                locale=Locale("ru"),
                message_id_to_edit=42,
            )
        assert ui.show.call_args.kwargs["message_id_to_edit"] == 42


# ==================== Хэндлеры: список и пагинация ====================

class TestWorkersHandlers:
    async def test_main_menu_renders_page_1(self):
        cb = _callback("admin_workers")
        st = _fsm_state()
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await route_workers_main_menu(
                callback=cb,
                admin_worker_service=AsyncMock(),
                main_admin_ids=[10],
                state=st,
                locale=Locale("ru"),
            )
        st.clear.assert_awaited_once()
        ui.show_list.assert_awaited_once()
        assert ui.show_list.call_args.kwargs["page"] == 1
        assert ui.show_list.call_args.kwargs["main_admin_ids"] == [10]

    async def test_page_navigation(self):
        cb = _callback("admin_workers_page:3")
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await route_workers_page(
                callback=cb,
                admin_worker_service=AsyncMock(),
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        ui.show_list.assert_awaited_once()
        assert ui.show_list.call_args.kwargs["page"] == 3

    async def test_page_invalid_data_ignored(self):
        cb = _callback("admin_workers_page:abc")
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await route_workers_page(
                callback=cb,
                admin_worker_service=AsyncMock(),
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        ui.show_list.assert_not_awaited()
        cb.answer.assert_awaited_once()


# ==================== Хэндлеры: добавление (FSM) ====================

class TestWorkerAddFSM:
    async def test_add_button_starts_fsm(self):
        cb = _callback("admin_worker_add")
        st = _fsm_state()
        await route_worker_add(callback=cb, state=st, locale=Locale("ru"))
        st.set_state.assert_awaited_once_with(AdminWorkerState.add_id)
        cb.message.answer.assert_awaited_once()
        st.update_data.assert_awaited_once()
        data = st.update_data.call_args.kwargs
        assert data["menu_message_id"] == 42
        assert "prompt_message_id" in data

    async def test_invalid_id_clears_state(self):
        msg = _message("abc")
        st = _fsm_state({"prompt_message_id": 43})
        await handle_worker_add_id(
            message=msg, state=st, admin_ids=[10], locale=Locale("ru")
        )
        st.clear.assert_awaited_once()
        msg.answer.assert_awaited_once()  # ошибка
        msg.delete.assert_not_awaited()

    async def test_duplicate_id_rejected(self):
        msg = _message("10")
        st = _fsm_state({"prompt_message_id": 43})
        await handle_worker_add_id(
            message=msg, state=st, admin_ids=[10], locale=Locale("ru")
        )
        st.clear.assert_awaited_once()
        msg.answer.assert_awaited_once()  # «уже работник»

    async def test_valid_id_moves_to_position_step(self):
        msg = _message("100")
        st = _fsm_state({"prompt_message_id": 43, "menu_message_id": 42})
        await handle_worker_add_id(
            message=msg, state=st, admin_ids=[10], locale=Locale("ru")
        )
        st.clear.assert_not_awaited()
        st.set_state.assert_awaited_once_with(AdminWorkerState.add_position)
        # Промпт и ввод удалены
        msg.bot.delete_message.assert_awaited_once_with(1, 43)
        msg.delete.assert_awaited_once()
        # Новый промпт (должность) + сохранённый telegram_id
        data = st.update_data.call_args.kwargs
        assert data["telegram_id"] == 100
        assert data["menu_message_id"] == 42

    async def test_position_saved_and_list_redrawn(self):
        msg = _message("Менеджер")
        st = _fsm_state(
            {"telegram_id": 100, "menu_message_id": 42, "prompt_message_id": 43}
        )
        service = AsyncMock()
        worker = SimpleNamespace(telegram_id=100, position="Менеджер")
        service.add_worker = AsyncMock(return_value=(worker, None))
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await handle_worker_add_position(
                message=msg,
                state=st,
                admin_worker_service=service,
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        st.clear.assert_awaited_once()
        service.add_worker.assert_awaited_once()
        assert service.add_worker.call_args.kwargs["telegram_id"] == 100
        assert service.add_worker.call_args.kwargs["position"] == "Менеджер"
        # Сервису передаётся только env-админ, а не объединённый список
        assert service.add_worker.call_args.kwargs["main_admin_ids"] == [10]
        msg.answer.assert_awaited_once()  # успех (self-destruct)
        ui.show_list.assert_awaited_once()
        assert ui.show_list.call_args.kwargs["message_id_to_edit"] == 42
        assert ui.show_list.call_args.kwargs["main_admin_ids"] == [10]

    async def test_position_error_no_redraw(self):
        msg = _message("Менеджер")
        st = _fsm_state(
            {"telegram_id": 100, "menu_message_id": 42, "prompt_message_id": 43}
        )
        service = AsyncMock()
        service.add_worker = AsyncMock(return_value=(None, "already_admin"))
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await handle_worker_add_position(
                message=msg,
                state=st,
                admin_worker_service=service,
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        msg.answer.assert_awaited_once()  # ошибка (self-destruct)
        ui.show_list.assert_not_awaited()


# ==================== Хэндлеры: удаление ====================

class TestWorkerDelete:
    async def test_delete_shows_confirm_screen(self):
        cb = _callback("admin_worker_del:100")
        repo = AsyncMock()
        repo.get_worker_by_telegram_id = AsyncMock(
            return_value=SimpleNamespace(telegram_id=100, position="Менеджер")
        )
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_delete_confirm = AsyncMock()
            await route_worker_delete(
                callback=cb, admin_repo=repo, locale=Locale("ru")
            )
        ui.show_delete_confirm.assert_awaited_once()
        assert ui.show_delete_confirm.call_args.kwargs["telegram_id"] == 100
        assert ui.show_delete_confirm.call_args.kwargs["position"] == "Менеджер"
        assert ui.show_delete_confirm.call_args.kwargs["message_id_to_edit"] == 42

    async def test_delete_not_found_alert(self):
        cb = _callback("admin_worker_del:999")
        repo = AsyncMock()
        repo.get_worker_by_telegram_id = AsyncMock(return_value=None)
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_delete_confirm = AsyncMock()
            await route_worker_delete(
                callback=cb, admin_repo=repo, locale=Locale("ru")
            )
        ui.show_delete_confirm.assert_not_awaited()
        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.kwargs.get("show_alert") is True

    async def test_confirm_delete_success(self):
        cb = _callback("admin_worker_del_confirm:100")
        service = AsyncMock()
        service.remove_worker = AsyncMock(return_value=(True, None))
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await route_worker_delete_confirm(
                callback=cb,
                admin_worker_service=service,
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        service.remove_worker.assert_awaited_once()
        # Сервису передаётся только env-админ (иначе работника из БД
        # нельзя будет удалить — он «главный»)
        assert service.remove_worker.call_args.kwargs["main_admin_ids"] == [10]
        cb.message.answer.assert_awaited_once()  # успех (self-destruct)
        ui.show_list.assert_awaited_once()  # возврат к списку in-place
        assert ui.show_list.call_args.kwargs["message_id_to_edit"] == 42
        assert ui.show_list.call_args.kwargs["main_admin_ids"] == [10]

    async def test_confirm_delete_main_admin_forbidden(self):
        """Даже при поддельном callback главный админ не удаляется."""
        cb = _callback("admin_worker_del_confirm:10")
        service = AsyncMock()
        service.remove_worker = AsyncMock(return_value=(False, "main_admin"))
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await route_worker_delete_confirm(
                callback=cb,
                admin_worker_service=service,
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        cb.message.answer.assert_awaited_once()  # «нельзя удалить»
        ui.show_list.assert_awaited_once()  # возврат к списку

    async def test_confirm_delete_not_found(self):
        cb = _callback("admin_worker_del_confirm:999")
        service = AsyncMock()
        service.remove_worker = AsyncMock(return_value=(False, "not_found"))
        with patch(
            "shopcrm_bot.handlers.admin.workers.workers.WorkersUI"
        ) as ui:
            ui.show_list = AsyncMock()
            await route_worker_delete_confirm(
                callback=cb,
                admin_worker_service=service,
                main_admin_ids=[10],
                locale=Locale("ru"),
            )
        cb.message.answer.assert_awaited_once()  # «не найден»
        ui.show_list.assert_awaited_once()


# ==================== Клавиатуры ====================

class TestWorkersKeyboards:
    def _kb(self):
        return Locale("ru").keyboards

    def test_list_kb_no_button_for_main_admin(self):
        kb = self._kb().get_workers_list_kb(
            workers=[_entry(10, is_main=True), _entry(100, "Менеджер")],
            current_page=1,
            total_pages=1,
        )
        callbacks = _kb_callbacks(kb)
        assert "admin_worker_del:100" in callbacks
        assert "admin_worker_del:10" not in callbacks
        assert "admin_worker_add" in callbacks
        assert "admin_main_menu" in callbacks

    def test_confirm_kb_callbacks(self):
        kb = self._kb().get_worker_delete_confirm_kb(telegram_id=100)
        callbacks = _kb_callbacks(kb)
        assert "admin_worker_del_confirm:100" in callbacks
        assert "admin_workers" in callbacks  # отмена -> список


# ==================== Middleware: доступ из БД ====================

class TestMiddlewareAdminIds:
    """Новый работник из БД мгновенно попадает в admin_ids."""

    def _make_middleware(self, monkeypatch, worker_ids: list[int]):
        from datetime import datetime

        import shopcrm_bot.middlewares.db as db_mw
        from aiogram.types import Chat, Message
        from aiogram.types import User as TgUser
        from shopcrm_bot.middlewares.db import DbSessionMiddleware
        from shopcrm_core.db.models.user import User

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        pool = MagicMock(return_value=session)

        user_repo = AsyncMock()
        user_repo.get_or_create_user = AsyncMock(
            return_value=User(id=100, language="ru")
        )

        monkeypatch.setattr(db_mw, "UserRepository", lambda s: user_repo)
        monkeypatch.setattr(db_mw, "AdminRepository", lambda s: AsyncMock())
        monkeypatch.setattr(db_mw, "ShopRepository", lambda s: AsyncMock())
        monkeypatch.setattr(db_mw, "AdminShopService", lambda r: AsyncMock())
        monkeypatch.setattr(db_mw, "AdminUserService", lambda r: AsyncMock())

        worker_service = AsyncMock()
        worker_service.get_admin_ids = AsyncMock(
            side_effect=lambda main: list(dict.fromkeys([*main, *worker_ids]))
        )
        monkeypatch.setattr(db_mw, "AdminWorkerService", lambda r: worker_service)

        msg = Message(
            message_id=1,
            date=datetime(2026, 1, 1),
            chat=Chat(id=100, type="private"),
            from_user=TgUser(id=100, is_bot=False, first_name="Test"),
            text="/start",
        )
        return DbSessionMiddleware(session_pool=pool), msg

    async def test_db_workers_in_admin_ids(self, monkeypatch):
        from shopcrm_bot.config import config

        mw, msg = self._make_middleware(monkeypatch, worker_ids=[777, 888])

        captured = {}

        async def handler(event, data):
            captured["admin_ids"] = data["admin_ids"]
            captured["main_admin_ids"] = data["main_admin_ids"]
            return "ok"

        result = await mw(handler, msg, {"bot": AsyncMock()})

        assert result == "ok"
        # admin_ids — объединённый (env + БД): для контроля доступа
        assert set(config.ADMIN_ID) <= set(captured["admin_ids"])
        assert 777 in captured["admin_ids"]
        assert 888 in captured["admin_ids"]
        # main_admin_ids — только env: для раздела «Работники».
        # Регрессия: если сюда попадут работники из БД, они станут
        # «главными» и будут дублироваться в списке.
        assert captured["main_admin_ids"] == list(config.ADMIN_ID)
        assert 777 not in captured["main_admin_ids"]
        assert 888 not in captured["main_admin_ids"]

