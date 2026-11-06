"""Тесты единой клиентской карточки заказа (Locale.format_order).

Карточка должна выглядеть одинаково на всех клиентских экранах:
подтверждение после оформления, просмотр заказа, запрос оплаты.
Поля «адрес доставки» и «комментарий» показываются только если заполнены,
разделители-линии в клиентской карточке отсутствуют.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from shopcrm_core.locales.locale import Locale


def _make_item(name: str = "Tea", price: float = 3.0, qty: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        product=SimpleNamespace(id=1, name=name),
        product_id=1,
        price_at_purchase=price,
        quantity=qty,
    )


def _make_order(**overrides) -> SimpleNamespace:
    base = dict(
        id=13,
        items=[_make_item()],
        delivery_price=0,
        total_price=3.0,
        delivery_address=None,
        delivery_address_type=None,
        user_comment=None,
        created_at=datetime(2026, 10, 27, 1, 52),
        status="pending",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_locale_cache():
    Locale._cached_locales = None
    yield
    Locale._cached_locales = None


class TestClientOrderCard:
    def test_details_hide_address_and_comment_when_absent(self):
        """Без адреса и комментария — строк нет, fallback «Not specified» не показываем."""
        loc = Locale(lang="en")
        text = loc.format_order(_make_order(), template_key="client.user_order_details")
        assert "Delivery Address" not in text
        assert "Comment" not in text
        assert "Not specified" not in text

    def test_details_show_address_and_comment_when_present(self):
        loc = Locale(lang="en")
        order = _make_order(delivery_address="123 Main St", user_comment="Ring the bell")
        text = loc.format_order(order, template_key="client.user_order_details")
        assert "📍 <b>Delivery Address:</b> 123 Main St" in text
        assert "💬 <b>Comment:</b> Ring the bell" in text

    def test_details_show_only_present_field(self):
        """Заполнен только адрес — строка комментария отсутствует."""
        loc = Locale(lang="en")
        order = _make_order(delivery_address="123 Main St")
        text = loc.format_order(order, template_key="client.user_order_details")
        assert "📍 <b>Delivery Address:</b> 123 Main St" in text
        assert "Comment" not in text

    def test_no_separator_lines_in_client_templates(self):
        """В клиентских карточках нет линий-разделителей ━."""
        loc = Locale(lang="en")
        order = _make_order(delivery_address="123 Main St", user_comment="Hi")
        for template_key in (
            "client.user_order_details",
            "client.user_checkout_confirm",
            "client.order_payment_request_text",
        ):
            kwargs = {"payment_details": "Bank: X"} if template_key.endswith("request_text") else {}
            text = loc.format_order(order, template_key=template_key, **kwargs)
            assert "━" not in text, f"Разделитель найден в шаблоне {template_key}"

    def test_checkout_confirm_keeps_header_and_same_card(self):
        """Checkout: шапка «placed successfully» + та же карточка, что в деталях заказа."""
        loc = Locale(lang="en")
        order = _make_order(delivery_address="123 Main St", user_comment="Hi")
        details = loc.format_order(order, template_key="client.user_order_details")
        confirm = loc.format_order(order, template_key="client.user_checkout_confirm")
        assert confirm.startswith("✅ <b>Order #13 placed successfully!</b>")
        assert details in confirm

    def test_payment_request_contains_same_card_body(self):
        """Запрос оплаты: то же тело карточки (без строки «🧾 Order #») + блок реквизитов."""
        loc = Locale(lang="en")
        order = _make_order(delivery_address="123 Main St", user_comment="Hi")
        details = loc.format_order(order, template_key="client.user_order_details")
        card_body = details.split("\n", 1)[1]  # без строки «🧾 Order #13»
        payment = loc.format_order(
            order, template_key="client.order_payment_request_text", payment_details="Bank: X"
        )
        assert card_body in payment
        assert "💳 <b>Payment Details:</b>\nBank: X" in payment

    def test_ru_templates_render(self):
        """Русская локаль: карточка рендерится без XXX и без пустых плейсхолдеров."""
        loc = Locale(lang="ru")
        order = _make_order(delivery_address="ул. Ленина, 1", user_comment="Позвонить")
        for template_key in (
            "client.user_order_details",
            "client.user_checkout_confirm",
            "client.order_payment_request_text",
        ):
            kwargs = {"payment_details": "Банк: X"} if template_key.endswith("request_text") else {}
            text = loc.format_order(order, template_key=template_key, **kwargs)
            assert "XXX" not in text
            assert "{info_block}" not in text
            assert "📍 <b>Адрес доставки:</b> ул. Ленина, 1" in text
            assert "💬 <b>Комментарий:</b> Позвонить" in text
