"""Сервис CSV-экспорта заказов для администратора.

Бизнес-логика формирования CSV отделена от Telegram-хэндлеров:
хэндлер только получает заказы из репозитория и отправляет файл.
"""
import csv
import io
from datetime import datetime

from shopcrm_core.db.models.order import Order

# Заголовки CSV (порядок колонок = порядок полей в строке)
CSV_HEADERS = [
    "id",
    "created_at",
    "user_id",
    "status",
    "is_paid",
    "items",
    "items_count",
    "total_price",
    "delivery_address",
    "user_comment",
]


def _format_items(order: Order) -> str:
    """Состав заказа в формате «Название xкол-во; Название xкол-во»."""
    parts = []
    for item in order.items or []:
        name = getattr(item.product, "name", None) or f"product_{item.product_id}"
        parts.append(f"{name} x{item.quantity}")
    return "; ".join(parts)


def build_orders_csv(orders: list[Order]) -> str:
    """Формирует содержимое CSV из списка заказов (одна строка на заказ)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)

    for order in orders:
        writer.writerow([
            order.id,
            order.created_at.isoformat(sep=" ", timespec="minutes") if order.created_at else "",
            order.user_id,
            order.status,
            "yes" if order.is_paid else "no",
            _format_items(order),
            sum(item.quantity for item in order.items or []),
            f"{float(order.total_price):.2f}",
            order.delivery_address or "",
            order.user_comment or "",
        ])

    return output.getvalue()


def build_export_filename(status: str, now: datetime | None = None) -> str:
    """Имя CSV-файла: orders_{status}_{YYYY-MM-DD}.csv."""
    now = now or datetime.now()
    return f"orders_{status}_{now:%Y-%m-%d}.csv"
