"""Тесты сервиса CSV-экспорта заказов."""
import csv
import io
from datetime import datetime

from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import Order
from shopcrm_core.constants import OrderStatus
from shopcrm_bot.services.csv_export_service import (
    CSV_HEADERS,
    build_export_filename,
    build_orders_csv,
)


class TestBuildOrdersCsv:
    """build_orders_csv — одна строка на заказ, корректные колонки."""

    async def _create_order_for(self, repo, session, user, product, quantity=1) -> Order:
        """Вспомогательный: создаёт заказ для user через корзину."""
        session.add(CartItem(user_id=user.id, product_id=product.id, quantity=quantity))
        await session.commit()
        order = await repo.create_order_from_cart(user_id=user.id)
        assert order is not None
        return order

    async def test_csv_contains_header_and_row(self, repo, session, user_a, product_a):
        """Заказ в статусе PENDING: строка CSV содержит все ключевые поля."""
        order = await self._create_order_for(repo, session, user_a, product_a, quantity=2)

        content = build_orders_csv([order])
        rows = list(csv.reader(io.StringIO(content)))
        assert rows[0] == CSV_HEADERS
        assert len(rows) == 2

        row = dict(zip(CSV_HEADERS, rows[1]))
        assert row["id"] == str(order.id)
        assert row["user_id"] == str(user_a.id)
        assert row["status"] == OrderStatus.PENDING.value
        assert row["is_paid"] == "no"
        assert row["items_count"] == "2"
        assert row["total_price"] == f"{float(order.total_price):.2f}"
        assert product_a.name in row["items"]

    async def test_csv_multiple_orders(self, repo, session, user_a, user_b, product_a):
        """Несколько заказов: по строке на каждый."""
        order_a = await self._create_order_for(repo, session, user_a, product_a)
        order_b = await self._create_order_for(repo, session, user_b, product_a)

        content = build_orders_csv([order_a, order_b])
        rows = list(csv.reader(io.StringIO(content)))
        assert len(rows) == 3  # заголовок + 2 заказа

    async def test_csv_empty_list(self):
        """Пустой список: только заголовок."""
        content = build_orders_csv([])
        rows = list(csv.reader(io.StringIO(content)))
        assert rows == [CSV_HEADERS]


class TestBuildExportFilename:
    """build_export_filename — orders_{status}_{YYYY-MM-DD}.csv."""

    def test_filename_with_status_and_date(self):
        now = datetime(2025, 6, 15, 12, 30)
        assert build_export_filename("pending", now=now) == "orders_pending_2025-06-15.csv"

    def test_filename_all(self):
        now = datetime(2025, 1, 1)
        assert build_export_filename("all", now=now) == "orders_all_2025-01-01.csv"
