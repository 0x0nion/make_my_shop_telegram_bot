"""Расчёт стоимости заказа со скидкой (единый источник формул).

Правила:
- ``discount_percent`` — снапшот персональной скидки покупателя (0–100)
  на момент оформления заказа, хранится в ``orders.discount_percent``.
- Скидка применяется **только к товарам**, не к доставке.
- Сумма скидки не хранится, а выводится из текущего состава заказа:
  ``items_sum * discount_percent / 100``. При изменении состава заказа
  (админ добавил/убрал позицию) процент сохраняется, сумма пересчитывается
  пропорционально.
- Округления нет: цены хранятся с точностью до 18 знаков (crypto-friendly),
  отображение — задача ``format_price``.
"""


def calc_items_sum(order_items) -> float:
    """Сумма позиций заказа: Σ quantity * price_at_purchase."""
    return sum(
        int(item.quantity) * float(item.price_at_purchase)
        for item in (order_items or [])
    )


def calc_discount_amount(items_sum: float, discount_percent: float) -> float:
    """Сумма скидки в деньгах: items_sum * percent / 100.

    Принимает и float, и Decimal (цены в рендере считаются в Decimal).
    """
    return float(items_sum) * float(discount_percent or 0) / 100


def calc_order_total(
    items_sum: float, delivery_price: float, discount_percent: float
) -> float:
    """Итог заказа: товары − скидка + доставка."""
    return (
        float(items_sum)
        - calc_discount_amount(items_sum, discount_percent)
        + float(delivery_price or 0)
    )


def format_discount_percent(value: float) -> str:
    """Форматирует процент скидки без хвостовых нулей: 10.0 -> "10", 15.5 -> "15.5"."""
    return f"{float(value or 0):g}"


def format_discount_marker(discount_percent: float) -> str:
    """Маркер скидки для списков/кнопок: " 🏷️15%" при скидке > 0, иначе "".

    Пример строки списка: "ID: 123 | 13.50 $ 🏷️15% - Ожидает".
    """
    percent = float(discount_percent or 0)
    if percent <= 0:
        return ""
    return f" 🏷️{format_discount_percent(percent)}%"
