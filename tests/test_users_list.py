"""Тесты раздела «Юзеры»: список, поиск по ID, карточка, скидка."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from shopcrm_bot.handlers.admin.users.card import (
    handle_user_discount_input,
    render_user_card,
)
from shopcrm_bot.handlers.admin.users.list import (
    PAGE_SIZE,
    handle_users_find_input,
    render_users_list,
)
from shopcrm_core.services.validation import validate_discount


def _callback(data: str = "admin_users") -> AsyncMock:
    cb = AsyncMock()
    cb.data = data
    cb.from_user = SimpleNamespace(id=1, language="ru")
    cb.message.message_id = 42
    return cb


def _user(
        id: int = 100,
        first_name: str | None = "Иван",
        username: str | None = "ivan",
        orders: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        first_name=first_name,
        username=username,
        orders=list(range(orders)),
    )


def _order(status: str = "completed", total_price: float = 100.0) -> SimpleNamespace:
    return SimpleNamespace(status=status, total_price=total_price)


def _card_user(
        id: int = 100,
        first_name: str | None = "Иван",
        username: str | None = "ivan",
        language: str | None = "ru",
        role: str = "client",
        created_at: datetime | None = None,
        discount: float = 0.0,
        orders: list | None = None,
        active_orders_count: int = 0,
) -> SimpleNamespace:
    """Мок пользователя для карточки (с полными полями)."""
    return SimpleNamespace(
        id=id,
        first_name=first_name,
        username=username,
        language=language,
        role=role,
        created_at=created_at,
        discount=discount,
        orders=orders or [],
        active_orders_count=active_orders_count,
    )


def _discount_message(text: str) -> AsyncMock:
    """Мок сообщения-ввода скидки (с bot.delete_message и delete)."""
    msg = AsyncMock()
    msg.text = text
    msg.chat = SimpleNamespace(id=1)
    msg.bot = AsyncMock()
    msg.delete = AsyncMock()
    msg.answer = AsyncMock(return_value=AsyncMock())
    return msg


def _fsm_state(data: dict) -> AsyncMock:
    st = AsyncMock()
    st.get_data = AsyncMock(return_value=data)
    st.clear = AsyncMock()
    return st


def _repo(users: list, total: int | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_users_count = AsyncMock(
        return_value=total if total is not None else len(users)
    )
    repo.get_users_page = AsyncMock(return_value=users)
    repo.get_user_by_id = AsyncMock(return_value=users[0] if users else None)
    return repo


def _message(text: str) -> AsyncMock:
    msg = AsyncMock()
    msg.text = text
    msg.from_user = SimpleNamespace(id=1, language="ru")
    return msg


def _kb_callbacks(markup) -> list[str]:
    """Все callback_data клавиатуры в порядке строк."""
    return [
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
    ]


async def _render(repo, data: str = "admin_users", page: int = 1) -> tuple[str, object]:
    """Запускает render_users_list и возвращает (текст, клавиатура)."""
    from shopcrm_bot.locales import Locale

    with patch("shopcrm_bot.handlers.admin.users.list.UIManager") as ui:
        ui.show = AsyncMock()
        await render_users_list(_callback(data), repo, page, locale=Locale("ru"))
    kwargs = ui.show.call_args.kwargs
    return kwargs["text"], kwargs["reply_markup"]


class TestUsersList:
    async def test_page_size_is_five(self):
        assert PAGE_SIZE == 5

    async def test_list_renders_users_with_mini_data(self):
        """Каждый юзер — 1 строка: ID, имя, @username, кол-во заказов."""
        users = [
            _user(id=100, first_name="Иван", username="ivan", orders=3),
            _user(id=200, first_name=None, username="anna", orders=0),
        ]
        repo = _repo(users)
        text, _ = await _render(repo)

        assert "Список пользователей" in text
        assert "ID: <code>100</code> | Иван | @ivan | 📦 3" in text
        # Без имени — «—», username остаётся
        assert "ID: <code>200</code> | — | @anna | 📦 0" in text

    async def test_list_empty(self):
        repo = _repo([], total=0)
        text, _ = await _render(repo)
        assert "Пользователи не найдены." in text

    async def test_user_button_callback_contains_id_and_page(self):
        users = [_user(id=100)]
        repo = _repo(users)
        _, markup = await _render(repo)

        callbacks = _kb_callbacks(markup)
        assert "admin_user_card:100:1" in callbacks

    async def test_find_and_back_buttons_present(self):
        users = [_user(id=100)]
        repo = _repo(users)
        _, markup = await _render(repo)

        callbacks = _kb_callbacks(markup)
        assert "admin_users_find" in callbacks
        assert "admin_main_menu" in callbacks

    async def test_circular_pagination_first_page(self):
        """Со 1-й страницы «⬅️» ведёт на последнюю, «➡️» — на 2-ю."""
        users = [_user(id=i) for i in range(1, 6)]
        repo = _repo(users, total=12)  # 12 юзеров -> 3 страницы
        _, markup = await _render(repo, data="admin_users", page=1)

        callbacks = _kb_callbacks(markup)
        assert "admin_users_page:3" in callbacks  # prev -> последняя
        assert "admin_users_page:2" in callbacks  # next
        assert "noop" in callbacks  # индикатор страницы

        page_texts = [
            btn.text
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "1/3" in page_texts

    async def test_circular_pagination_last_page(self):
        """С последней страницы «➡️» ведёт на 1-ю."""
        users = [_user(id=i) for i in range(11, 13)]
        repo = _repo(users, total=12)
        _, markup = await _render(repo, data="admin_users_page:3", page=3)

        callbacks = _kb_callbacks(markup)
        assert "admin_users_page:2" in callbacks  # prev
        assert "admin_users_page:1" in callbacks  # next -> первая

    async def test_page_clamped_to_total(self):
        """Запрос страницы за пределами диапазона зацикливается на 1-ю."""
        users = [_user(id=100)]
        repo = _repo(users, total=5)  # 1 страница
        await _render(repo, data="admin_users_page:99", page=99)

        repo.get_users_page.assert_awaited_once_with(limit=5, offset=0)


class TestUsersFindById:
    async def _handle(self, text: str, repo) -> AsyncMock:
        """Запускает handle_users_find_input с моком render_user_card."""
        from shopcrm_bot.locales import Locale

        state = AsyncMock()
        with patch(
            "shopcrm_bot.handlers.admin.users.list.render_user_card"
        ) as card:
            await handle_users_find_input(
                _message(text), state, repo, Locale("ru")
            )
        return card

    async def test_invalid_input(self):
        repo = _repo([])
        card = await self._handle("abc", repo)
        card.assert_not_awaited()

    async def test_user_not_found(self):
        repo = _repo([])
        repo.get_user_by_id = AsyncMock(return_value=None)
        card = await self._handle("999", repo)
        card.assert_not_awaited()

    async def test_user_found_opens_card(self):
        target = _user(id=100)
        repo = _repo([target])
        repo.get_user_by_id = AsyncMock(return_value=target)
        card = await self._handle("100", repo)
        card.assert_awaited_once()
        assert card.call_args.kwargs["target"].id == 100


class TestUserCard:
    async def _render_card(self, target, page: int = 2) -> dict:
        from shopcrm_bot.locales import Locale

        with patch("shopcrm_bot.handlers.admin.users.card.UIManager") as ui:
            ui.show = AsyncMock()
            await render_user_card(
                event=_callback("admin_user_card:100:2"),
                target=target,
                page=page,
                locale=Locale("ru"),
            )
        return ui.show.call_args.kwargs

    async def test_card_full_text(self):
        """Карточка: имя, @username, дата, язык, роль, статус, заказы, потрачено, скидка."""
        target = _card_user(
            id=100,
            first_name="Иван",
            username="ivan",
            language="ru",
            role="client",
            created_at=datetime(2026, 11, 12),
            discount=15.5,
            orders=[
                _order("completed", 100.0),
                _order("cancelled", 50.0),
                _order("processing", 25.5),
            ],
            active_orders_count=1,
        )
        kwargs = await self._render_card(target)
        text = kwargs["text"]

        assert "Пользователь #100" in text
        assert "Имя: Иван" in text
        assert "@username: @ivan" in text
        assert "Зарегистрирован: 12.11.2026" in text
        assert "Язык: ru" in text
        assert "Роль: клиент" in text
        assert "Статус: ✅ Активен (1 активных заказов)" in text
        assert "Заказов: 3" in text
        # «Потрачено» не считает отменённые: 100 + 25.5 = 125.50
        assert "Потрачено: 125.50" in text
        assert "Скидка: 15.5%" in text

    async def test_card_keyboard_discount_and_back(self):
        """Кнопки: «Изменить скидку» + «Назад» в список на ту же страницу."""
        target = _card_user(id=100)
        kwargs = await self._render_card(target, page=2)

        assert _kb_callbacks(kwargs["reply_markup"]) == [
            "admin_user_discount:100:2",
            "admin_users_page:2",
        ]

    async def test_card_inactive_and_empty_profile(self):
        """Неактивен, без имени/username — «—», скидка 0%."""
        target = _card_user(
            id=200,
            first_name=None,
            username=None,
            created_at=None,
            active_orders_count=0,
        )
        kwargs = await self._render_card(target)
        text = kwargs["text"]

        assert "Статус: ⚪ Неактивен" in text
        assert "Имя: —" in text
        assert "@username" not in text
        assert "Зарегистрирован" not in text
        assert "Скидка: 0%" in text
        assert "Потрачено: 0.00" in text

    async def test_card_admin_role(self):
        target = _card_user(id=300, role="admin")
        kwargs = await self._render_card(target)
        assert "Роль: администратор" in kwargs["text"]


class TestValidateDiscount:
    async def test_valid_integer(self):
        d, err = validate_discount("10", "ru")
        assert d == 10.0 and err is None

    async def test_valid_zero(self):
        d, err = validate_discount("0", "ru")
        assert d == 0.0 and err is None

    async def test_valid_hundred(self):
        d, err = validate_discount("100", "ru")
        assert d == 100.0 and err is None

    async def test_valid_decimal_comma(self):
        d, err = validate_discount("15,5", "ru")
        assert d == 15.5 and err is None

    async def test_too_big(self):
        d, err = validate_discount("101", "ru")
        assert d is None and err is not None

    async def test_negative(self):
        d, err = validate_discount("-5", "ru")
        assert d is None and err is not None

    async def test_not_a_number(self):
        d, err = validate_discount("abc", "ru")
        assert d is None and err is not None


class TestSetUserDiscount:
    async def test_set_discount(self, session, user_a):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository

        repo = AdminRepository(session)
        updated = await repo.set_user_discount(user_a.id, 15.5)
        assert updated is not None
        assert float(updated.discount) == 15.5

    async def test_set_discount_not_found(self, session):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository

        repo = AdminRepository(session)
        assert await repo.set_user_discount(999, 10.0) is None

    async def test_get_user_by_id_loads_orders(self, session, user_a):
        from shopcrm_core.db.models.order import Order
        from shopcrm_core.db.repositories.admin_repo import AdminRepository

        session.add(Order(user_id=user_a.id, total_price=100.0))
        await session.commit()

        repo = AdminRepository(session)
        user = await repo.get_user_by_id(user_a.id)
        assert user is not None
        assert len(user.orders) == 1


class TestDiscountInput:
    """FSM-флоу ввода скидки: промпт → валидация → сохранение → re-render."""

    _STATE_DATA = {
        "user_id": 100,
        "page": 2,
        "menu_message_id": 42,
        "prompt_message_id": 43,
    }

    async def _handle(self, text: str, service: AsyncMock) -> tuple:
        from shopcrm_bot.locales import Locale

        msg = _discount_message(text)
        st = _fsm_state(dict(self._STATE_DATA))
        user = SimpleNamespace(language="ru")
        with patch(
            "shopcrm_bot.handlers.admin.users.card.render_user_card"
        ) as card, patch(
            "shopcrm_bot.handlers.admin.users.card.self_destruct"
        ) as sd:
            await handle_user_discount_input(msg, st, service, user, Locale("ru"))
        return msg, st, card, sd

    async def test_invalid_input_no_save_no_render(self):
        """Невалидный ввод: ошибка, без сохранения и без re-render."""
        service = AsyncMock()
        service.set_user_discount = AsyncMock(return_value=None)

        msg, st, card, _ = await self._handle("abc", service)

        st.clear.assert_awaited_once()
        service.set_user_discount.assert_not_awaited()
        card.assert_not_awaited()
        msg.answer.assert_awaited_once()  # сообщение об ошибке

    async def test_valid_input_saves_and_renders(self):
        """Валидный ввод: сохранение + re-render карточки in-place."""
        target = _card_user(id=100, discount=10.0)
        service = AsyncMock()
        service.set_user_discount = AsyncMock(return_value=target)

        msg, st, card, _ = await self._handle("10", service)

        service.set_user_discount.assert_awaited_once_with(100, 10.0)
        card.assert_awaited_once()
        assert card.call_args.kwargs["message_id_to_edit"] == 42
        assert card.call_args.kwargs["page"] == 2
        # Промпт и ввод удалены
        msg.bot.delete_message.assert_awaited_once_with(1, 43)
        msg.delete.assert_awaited_once()

    async def test_valid_input_comma_decimal(self):
        """Запятая как разделитель: 15,5 -> 15.5."""
        target = _card_user(id=100, discount=15.5)
        service = AsyncMock()
        service.set_user_discount = AsyncMock(return_value=target)

        _, _, card, _ = await self._handle("15,5", service)

        service.set_user_discount.assert_awaited_once_with(100, 15.5)
        card.assert_awaited_once()

    async def test_user_not_found_no_render(self):
        """Юзер не найден: сообщение, без re-render."""
        service = AsyncMock()
        service.set_user_discount = AsyncMock(return_value=None)

        msg, _, card, _ = await self._handle("10", service)

        service.set_user_discount.assert_awaited_once_with(100, 10.0)
        card.assert_not_awaited()
        msg.answer.assert_awaited_once()  # «не найден»


class TestAdminUserService:
    async def test_get_user_card_found(self, session, user_a):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository
        from shopcrm_core.services.admin_user_service import AdminUserService

        service = AdminUserService(AdminRepository(session))
        user = await service.get_user_card(user_a.id)
        assert user is not None
        assert user.id == user_a.id

    async def test_get_user_card_not_found(self, session):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository
        from shopcrm_core.services.admin_user_service import AdminUserService

        service = AdminUserService(AdminRepository(session))
        assert await service.get_user_card(999) is None

    async def test_set_user_discount(self, session, user_a):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository
        from shopcrm_core.services.admin_user_service import AdminUserService

        service = AdminUserService(AdminRepository(session))
        updated = await service.set_user_discount(user_a.id, 25.0)
        assert updated is not None
        assert float(updated.discount) == 25.0

    async def test_set_user_discount_not_found(self, session):
        from shopcrm_core.db.repositories.admin_repo import AdminRepository
        from shopcrm_core.services.admin_user_service import AdminUserService

        service = AdminUserService(AdminRepository(session))
        assert await service.set_user_discount(999, 10.0) is None

