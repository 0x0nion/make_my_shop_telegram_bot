import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Locale:
    locale_path = Path(__file__).resolve().parent / "msg.json"

    def __init__(self, lang: str = "ru"):
        self.lang = lang
        self.locales: Dict[str, Any] = self._load_json()

    def _load_json(self) -> Dict[str, Any]:
        """Загружает полный словарь локализаций из msg.json."""
        try:
            with open(self.locale_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.critical(f"Can't open {self.locale_path}: {e}", exc_info=True)
            return {}

    def get_text(self, key: str) -> str:
        """
        Получает текст по ключу для текущего языка.
        Иерархия поиска: self.lang -> 'ru' -> 'en' -> 'XXX'.
        """
        key_data = self.locales.get(key)
        if not key_data or not isinstance(key_data, dict):
            logger.critical(f"[LOCALES] Key '{key}' not found or invalid in msg.json!")
            return "XXX"

        text = key_data.get(self.lang) or key_data.get("ru") or key_data.get("en")
        if text is None:
            logger.critical(f"[LOCALES] Translation for key '{key}' and lang '{self.lang}' not found!")
            return "XXX"

        return text

    def format_order(self, order, template_key: str = "user_checkout_confirm", **kwargs) -> str:
        """
        Универсальный метод форматирования любого чека / карточки заказа.

        Поддерживаемые плейсхолдеры в msg.json:
        {id}, {order_id}, {items}, {address_block}, {comment_block},
        {items_price}, {delivery_price}, {total_price}, + любые переданные **kwargs
        """
        item_lines = []
        items_price = 0.0

        for item in order.items:
            product_name = item.product.name if getattr(item, "product", None) else "Deleted Product"
            price = float(item.price_at_purchase)
            item_total = item.quantity * price
            items_price += item_total
            item_lines.append(
                f"• {product_name} — {item.quantity} x {price:.2f} $ = {item_total:.2f} $"
            )

        items_block = "\n".join(item_lines) if item_lines else "—"

        # Адрес и комментарий
        if getattr(order, "delivery_address", None):
            delivery_label = self.get_text("order_delivery_label")
            address_block = f"📍 {delivery_label} {order.delivery_address}\n\n"
        else:
            address_block = ""

        if getattr(order, "user_comment", None):
            comment_label = self.get_text("order_comment_label")
            comment_block = f"📝 {comment_label} {order.user_comment}\n\n"
        else:
            comment_block = ""

        # Расчет цен
        total_price = float(order.total_price) if getattr(order, "total_price", None) is not None else items_price
        delivery_price = float(getattr(order, "delivery_price", 0.0) or 0.0)

        template = self.get_text(template_key)

        # Собираем базовый словарь плейсхолдеров
        context = {
            "id": order.id,
            "order_id": order.id,
            "items": items_block,
            "address_block": address_block,
            "comment_block": comment_block,
            "items_price": items_price,
            "delivery_price": delivery_price,
            "total_price": total_price,
        }

        # Перекрываем/дополняем контекст внешними параметрами (например, payment_details)
        context.update(kwargs)

        return template.format(**context)

    def format_address(self, maps_url: str) -> str:
        template = self.get_text("user_address_link")
        return template.format(maps_url=maps_url)