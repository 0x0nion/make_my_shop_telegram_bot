"""Тесты локализованного отображения статуса в списке заказов администратора.

Заголовок списка и строки заказов показывают локализованную подпись статуса
(ту же, что в меню фильтров), а не сырое значение из БД.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from shopcrm_bot.handlers.admin.orders.list import render_orders_list


def _callback() -> AsyncMock:
    cb = AsyncMock()
    cb.data = "admin_orders_page:all:1"
    cb.message.message_id = 42
    return cb


def _user(lang: str = "ru") -> SimpleNamespace:
    return SimpleNamespace(language=lang)


def _order(id: int = 1, status: str = "pending", total_price=10) -> SimpleNamespace:
    return SimpleNamespace(id=id, status=status, total_price=total_price)


def _repo(orders: list, counts: dict | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_orders_count_by_statuses = AsyncMock(return_value=counts or {})
    repo.get_orders_by_status = AsyncMock(return_value=orders)
    return repo


async def _render(repo, user, status: str) -> str:
    """Запускает render_orders_list и возвращает отрисованный текст."""
    with patch("shopcrm_bot.handlers.admin.orders.list.UIManager") as ui:
        ui.show = AsyncMock()
        await render_orders_list(_callback(), repo, user, status, 1)
    return ui.show.call_args.kwargs["text"]


class TestOrdersListStatusLocalization:
    async def test_header_and_line_use_localized_status(self):
        """Заголовок и строка заказа показывают локализованную подпись."""
        repo = _repo([_order(status="pending")], counts={"pending": 1})
        text = await _render(repo, _user("ru"), "pending")
        assert "Создан / Ожидает" in text
        assert "pending" not in text

    async def test_header_all_uses_localized_all(self):
        """Фильтр «all» в заголовке показывается локализованным словом."""
        repo = _repo([], counts={})
        text = await _render(repo, _user("ru"), "all")
        assert "Список заказов (все)" in text
        assert "all" not in text

    async def test_line_localized_in_english(self):
        repo = _repo([_order(status="processing")], counts={"processing": 1})
        text = await _render(repo, _user("en"), "processing")
        assert "Processing" in text
        assert "processing" not in text