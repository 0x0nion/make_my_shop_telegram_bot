"""Тесты рендера корзины (render_cart).

Корзина выглядит так же, как карточка заказа у юзера:
- строка сверху — «Корзина» (без номера заказа, даты и статуса),
- строки «Адрес доставки» и «Комментарий» всегда присутствуют
  (это форма заполнения — с плейсхолдером, если не заполнены),
- позиции и расчёт стоимости — в том же формате, что и в заказе.
"""
from types import SimpleNamespace

import pytest

from shopcrm_core.locales.locale import Locale
from shopcrm_bot.handlers.client.cart.render_cart import render_cart
from shopcrm_bot.ui import UIManager


class FakeState:
    """Минимальный двойник FSMContext."""

    def __init__(self, data: dict | None = None):
        self._data = data or {}

    async def get_data(self):
        return self._data

    async def update_data(self, **kwargs):
        self._data.update(kwargs)


def _make_event(user_id: int = 100) -> SimpleNamespace:
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id))


@pytest.fixture(autouse=True)
def _reset_locale_cache():
    Locale._cached_locales = None
    yield
    Locale._cached_locales = None


@pytest.fixture
def captured_ui(monkeypatch):
    """Перехватывает текст, отправляемый через UIManager.show."""
    captured = {}

    async def fake_show(event, text, reply_markup=None, message_id_to_edit=None, **kwargs):
        captured["text"] = text
        captured["reply_markup"] = reply_markup
        return SimpleNamespace(message_id=42)

    monkeypatch.setattr(UIManager, "show", fake_show)
    return captured


class TestCartRender:
    async def test_cart_mirrors_order_card(
        self, repo, session, user_a, product_a, product_b, cart_with_items, captured_ui
    ):
        """Заголовок, позиции и расчёт стоимости — в формате карточки заказа."""
        await render_cart(_make_event(), repo, FakeState())

        text = captured_ui["text"]
        # Строка сверху — корзина; номера заказа, даты и статуса нет
        assert text.startswith("🛒 <b>Корзина</b>")
        assert "Заказ #" not in text
        assert "Дата:" not in text
        assert "Статус:" not in text

        # Позиции — тот же формат, что в заказе (нумерация + └)
        assert "🛒 <b>Состав корзины:</b>" in text
        assert "1. <b>Widget</b>\n   └ 2 шт. x 10 $ = <b>20 $</b>" in text
        assert "2. <b>Gadget</b>\n   └ 1 кг x 25.5 $ = <b>25.5 $</b>" in text

        # Расчёт стоимости — как в заказе
        assert "💰 <b>Расчёт стоимости:</b>" in text
        assert "🛒 Товары: 45.5 $" in text
        assert "🚚 Доставка: 0 $" in text
        assert "💵 Итого к оплате: <b>45.5 $</b>" in text

    async def test_address_and_comment_placeholders_when_empty(
        self, repo, session, user_a, product_a, product_b, cart_with_items, captured_ui
    ):
        """Адрес и комментарий не заполнены — строки есть, с плейсхолдерами."""
        await render_cart(_make_event(), repo, FakeState())

        text = captured_ui["text"]
        assert "📍 <b>Адрес доставки:</b> Не указан" in text
        assert "💬 <b>Комментарий:</b> Отсутствует" in text

    async def test_address_and_comment_shown_when_filled(
        self, repo, session, user_a, product_a, product_b, cart_with_items, captured_ui
    ):
        """Адрес и комментарий заполнены — показываются значения, без плейсхолдеров."""
        state = FakeState(
            {
                "delivery_address": "123 Main St",
                "delivery_address_type": "text",
                "user_comment": "Ring the bell",
            }
        )
        await render_cart(_make_event(), repo, state)

        text = captured_ui["text"]
        assert "📍 <b>Адрес доставки:</b> 123 Main St" in text
        assert "💬 <b>Комментарий:</b> Ring the bell" in text
        assert "Не указан" not in text
        assert "Отсутствует" not in text

    async def test_cart_message_id_saved_to_state(
        self, repo, session, user_a, product_a, product_b, cart_with_items, captured_ui
    ):
        """id отправленного сообщения сохраняется в FSM для последующего edit."""
        state = FakeState()
        await render_cart(_make_event(), repo, state)

        assert state._data.get("cart_message_id") == 42
