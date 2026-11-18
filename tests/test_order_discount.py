"""Тесты учёта персональной скидки в заказах.

Правила:
- скидка хранится снапшотом в ``orders.discount_percent`` на момент оформления;
- применяется только к товарам, не к доставке;
- сумма выводится: ``items_sum * discount_percent / 100``;
- итог: ``items_sum - discount_amount + delivery_price``;
- строка скидки показывается только при ``discount_percent > 0``.
"""
import csv
import io
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.locales.locale import Locale
from shopcrm_core.services.order_calc import (
    calc_discount_amount,
    calc_items_sum,
    calc_order_total,
    format_discount_marker,
    format_discount_percent,
)
from shopcrm_core.services.order_service import build_order_detail_text
from shopcrm_core.utils import format_price


# ---------------------------------------------------------------------
# 1. Чистые функции расчёта (order_calc)
# ---------------------------------------------------------------------

class TestOrderCalcFunctions:
    """order_calc — единый источник формул, без зависимостей от БД/Telegram."""

    def test_calc_items_sum(self):
        items = [
            SimpleNamespace(quantity=2, price_at_purchase=10.0),
            SimpleNamespace(quantity=1, price_at_purchase=25.5),
        ]
        assert calc_items_sum(items) == pytest.approx(45.5)

    def test_calc_items_sum_empty_and_none(self):
        assert calc_items_sum([]) == 0.0
        assert calc_items_sum(None) == 0.0

    def test_calc_discount_amount(self):
        assert calc_discount_amount(100.0, 15) == pytest.approx(15.0)
        assert calc_discount_amount(100.0, 0) == 0.0
        assert calc_discount_amount(100.0, None) == 0.0

    def test_calc_order_total_no_discount(self):
        """Без скидки: товары + доставка."""
        assert calc_order_total(100.0, 10.0, 0) == pytest.approx(110.0)

    def test_calc_order_total_with_discount(self):
        """Скидка только на товары: 100 - 15 + 10 = 95."""
        assert calc_order_total(100.0, 10.0, 15) == pytest.approx(95.0)

    def test_calc_order_total_discount_not_applied_to_delivery(self):
        """Скидка 100% обнуляет товары, но доставка остаётся."""
        assert calc_order_total(100.0, 10.0, 100) == pytest.approx(10.0)

    def test_calc_order_total_accepts_decimal(self):
        """items_price в рендере считается в Decimal — функции должны принимать."""
        from decimal import Decimal
        assert calc_order_total(Decimal("45.50"), 0, 10) == pytest.approx(40.95)

    def test_format_discount_percent(self):
        assert format_discount_percent(15.0) == "15"
        assert format_discount_percent(15.5) == "15.5"
        assert format_discount_percent(0) == "0"
        assert format_discount_percent(None) == "0"

    def test_format_discount_marker(self):
        assert format_discount_marker(0) == ""
        assert format_discount_marker(None) == ""
        assert format_discount_marker(15) == " 🏷️15%"
        assert format_discount_marker(15.5) == " 🏷️15.5%"


# ---------------------------------------------------------------------
# 2. Создание заказа со скидкой
# ---------------------------------------------------------------------

class TestCreateOrderWithDiscount:
    """create_order_from_cart: снапшот скидки и итог только по товарам."""

    async def test_order_snapshots_user_discount(self, repo, session, user_a, product_a):
        """Скидка юзера фиксируется снапшотом в заказе."""
        user_a.discount = 20
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=3))
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order is not None
        assert float(order.discount_percent) == pytest.approx(20.0)

    async def test_order_total_applies_discount_to_items_only(
        self, repo, session, user_a, product_a, product_b
    ):
        """Итог = товары - скидка + доставка(0). Скидка только на товары."""
        user_a.discount = 10
        session.add_all([
            CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),  # 20.00
            CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),  # 25.50
        ])
        await session.commit()
        # items_sum = 45.50, discount = 4.55, total = 40.95
        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order is not None
        assert float(order.total_price) == pytest.approx(40.95)

    async def test_order_without_discount_unchanged(
        self, repo, session, user_a, product_a, product_b
    ):
        """Без скидки итог = сумма товаров (discount_percent=0)."""
        session.add_all([
            CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),
            CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),
        ])
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)

        assert order is not None
        assert float(order.discount_percent) == pytest.approx(0.0)
        assert float(order.total_price) == pytest.approx(45.50)

    async def test_order_independent_of_later_discount_change(
        self, repo, session, user_a, product_a
    ):
        """После оформления изменение скидки юзера не влияет на заказ."""
        user_a.discount = 30
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))
        await session.commit()

        order = await repo.create_order_from_cart(user_id=user_a.id)
        total_at_creation = float(order.total_price)

        # Админ меняет скидку юзера уже после заказа
        user_a.discount = 0
        await session.commit()

        assert float(order.discount_percent) == pytest.approx(30.0)
        assert float(order.total_price) == pytest.approx(total_at_creation)


# ---------------------------------------------------------------------
# Вспомогательные двойники для рендера корзины
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# 3. Рендер корзины со скидкой
# ---------------------------------------------------------------------

class TestCartRenderDiscount:
    """Корзина показывает строку скидки и итог со скидкой до оформления."""

    @pytest.fixture(autouse=True)
    def _reset_locale_cache(self):
        Locale._cached_locales = None
        yield
        Locale._cached_locales = None

    @pytest.fixture
    def captured_ui(self, monkeypatch):
        from shopcrm_bot.ui import UIManager

        captured = {}

        async def fake_show(event, text, reply_markup=None, message_id_to_edit=None, **kwargs):
            captured["text"] = text
            captured["reply_markup"] = reply_markup
            return SimpleNamespace(message_id=42)

        monkeypatch.setattr(UIManager, "show", fake_show)
        return captured

    async def test_cart_shows_discount_line(
        self, repo, session, user_a, product_a, captured_ui
    ):
        """Скидка 15% на 1×Widget(10.00): строка скидки и итог 8.50."""
        from shopcrm_bot.handlers.client.cart.render_cart import render_cart

        user_a.discount = 15
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))
        await session.commit()

        await render_cart(_make_event(), repo, FakeState())

        text = captured_ui["text"]
        assert "Скидка (15%)" in text
        assert format_price(1.50) in text  # сумма скидки
        assert format_price(8.50) in text  # итог

    async def test_cart_without_discount_no_line(
        self, repo, session, user_a, product_a, captured_ui
    ):
        """Без скидки строки «Скидка» в корзине нет."""
        from shopcrm_bot.handlers.client.cart.render_cart import render_cart

        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))
        await session.commit()

        await render_cart(_make_event(), repo, FakeState())

        assert "Скидка" not in captured_ui["text"]


# ---------------------------------------------------------------------
# 4. Клиентская карточка заказа со скидкой
# ---------------------------------------------------------------------

class TestClientOrderCardDiscount:
    """Locale.format_order: строка скидки в клиентской карточке."""

    @pytest.fixture(autouse=True)
    def _reset_locale_cache(self):
        Locale._cached_locales = None
        yield
        Locale._cached_locales = None

    def _make_order(self, **overrides) -> SimpleNamespace:
        base = dict(
            id=13,
            items=[
                SimpleNamespace(
                    product=SimpleNamespace(id=1, name="Widget"),
                    product_id=1,
                    price_at_purchase=10.0,
                    quantity=1,
                )
            ],
            delivery_price=0,
            discount_percent=0,
            total_price=10.0,
            delivery_address=None,
            delivery_address_type=None,
            user_comment=None,
            created_at=datetime(2026, 10, 27, 1, 52),
            status="pending",
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_card_shows_discount_line(self):
        loc = Locale(lang="ru")
        order = self._make_order(discount_percent=15, total_price=8.50)
        text = loc.format_order(order, template_key="client.user_order_details")
        assert "Скидка (15%)" in text
        assert format_price(1.50) in text
        assert format_price(8.50) in text

    def test_card_without_discount_no_line(self):
        loc = Locale(lang="ru")
        order = self._make_order(discount_percent=0, total_price=10.0)
        text = loc.format_order(order, template_key="client.user_order_details")
        assert "Скидка" not in text

    def test_discount_line_between_items_and_delivery(self):
        """Строка скидки стоит между «Товары» и «Доставка»."""
        loc = Locale(lang="ru")
        order = self._make_order(discount_percent=15, total_price=8.50)
        text = loc.format_order(order, template_key="client.user_order_details")
        assert (
            text.index("Товары:")
            < text.index("Скидка")
            < text.index("Доставка:")
        )


# ---------------------------------------------------------------------
# 5. Админ-карточка заказа со скидкой
# ---------------------------------------------------------------------

class TestAdminOrderDetailDiscount:
    """build_order_detail_text: строка скидки в админ-карточке."""

    @pytest.fixture(autouse=True)
    def _reset_locale_cache(self):
        Locale._cached_locales = None
        yield
        Locale._cached_locales = None

    def _make_order(self, **overrides) -> SimpleNamespace:
        base = dict(
            id=42,
            user=SimpleNamespace(id=100, username="buyer"),
            items=[
                SimpleNamespace(
                    product=SimpleNamespace(id=1, name="Widget", unit="pc"),
                    product_id=1,
                    price_at_purchase=10.0,
                    quantity=1,
                )
            ],
            delivery_price=0,
            discount_percent=0,
            total_price=10.0,
            delivery_address=None,
            delivery_address_type=None,
            user_comment=None,
            manager_comment=None,
            created_at=datetime(2026, 1, 1, 12, 0),
            is_paid=False,
            payment_proof_type=None,
            payment_proof=None,
            status="pending",
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    async def _build(self, order, lang: str = "ru") -> str:
        repo = AsyncMock()
        repo.get_order_by_id = AsyncMock(return_value=order)
        text, _ = await build_order_detail_text(repo, 42, lang=lang)
        return text

    async def test_admin_card_shows_discount_line(self):
        order = self._make_order(discount_percent=15, total_price=8.50)
        text = await self._build(order)
        assert "Скидка (15%)" in text
        assert format_price(1.50) in text

    async def test_admin_card_without_discount_no_line(self):
        order = self._make_order(discount_percent=0, total_price=10.0)
        text = await self._build(order)
        assert "Скидка" not in text


# ---------------------------------------------------------------------
# 6. CSV-экспорт со скидкой
# ---------------------------------------------------------------------

class TestCsvExportDiscount:
    """build_orders_csv: колонки скидки и самосогласованный итог."""

    async def test_csv_has_discount_columns(self):
        from shopcrm_bot.services.csv_export_service import CSV_HEADERS

        for col in ("items_sum", "discount_percent", "discount_amount", "delivery_price"):
            assert col in CSV_HEADERS

    async def test_csv_discount_values(self, repo, session, user_a, product_a):
        from shopcrm_bot.services.csv_export_service import CSV_HEADERS, build_orders_csv

        user_a.discount = 10
        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2))  # 20.00
        await session.commit()
        order = await repo.create_order_from_cart(user_id=user_a.id)
        # items_sum=20.00, discount=2.00, delivery=0, total=18.00

        content = build_orders_csv([order])
        rows = list(csv.reader(io.StringIO(content)))
        row = dict(zip(CSV_HEADERS, rows[1], strict=True))

        assert row["items_sum"] == format_price(20.00)
        assert row["discount_percent"] == "10"
        assert row["discount_amount"] == format_price(2.00)
        assert row["delivery_price"] == format_price(0.0)
        assert row["total_price"] == format_price(18.00)

    async def test_csv_no_discount_zero(self, repo, session, user_a, product_a):
        from shopcrm_bot.services.csv_export_service import CSV_HEADERS, build_orders_csv

        session.add(CartItem(user_id=user_a.id, product_id=product_a.id, quantity=1))  # 10.00
        await session.commit()
        order = await repo.create_order_from_cart(user_id=user_a.id)

        content = build_orders_csv([order])
        rows = list(csv.reader(io.StringIO(content)))
        row = dict(zip(CSV_HEADERS, rows[1], strict=True))

        assert row["discount_percent"] == "0"
        assert row["discount_amount"] == format_price(0.0)
        assert row["total_price"] == format_price(10.00)
