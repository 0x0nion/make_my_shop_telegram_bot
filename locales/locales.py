import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from locales.currencies import get_currency_label, get_currency_symbol
from locales.units import get_unit_label

logger = logging.getLogger(__name__)


class SafeDict(dict):
    """Словарь для безопасного format_map(), защищает от KeyError."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


class Locale:
    locale_path = Path(__file__).resolve().parent / "msg.json"
    _cached_locales: Optional[Dict[str, Any]] = None

    def __init__(self, lang: str = "en"):
        self.lang = lang or "en"
        self.locales: Dict[str, Any] = self._get_locales()

    @classmethod
    def _get_locales(cls) -> Dict[str, Any]:
        """Загружает JSON один раз и кэширует его в памяти класса."""
        if cls._cached_locales is None:
            try:
                with open(cls.locale_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    cls._cached_locales = data if isinstance(data, dict) else {}
            except Exception as e:
                logger.critical(
                    f"[LOCALES] Can't open {cls.locale_path}: {e}", exc_info=True
                )
                cls._cached_locales = {}
        return cls._cached_locales

    @classmethod
    def reload_locales(cls) -> None:
        """Сброс кэша для горячей перезагрузки локалей без рестарта бота."""
        cls._cached_locales = None
        cls._get_locales()

    def get_text(self, key: str, **kwargs) -> str:
        """
        Получает текст по ключу. Иерархия: self.lang -> 'ru' -> 'en' -> 'XXX'.
        Если переданы kwargs, автоматически подставляет их через SafeDict.
        """
        key_data = self.locales.get(key)
        if not key_data or not isinstance(key_data, dict):
            logger.critical(
                f"[LOCALES] Key '{key}' not found or invalid in msg.json!"
            )
            return "XXX"

        text = (
            key_data.get(self.lang)
            or key_data.get("ru")
            or key_data.get("en")
        )
        if text is None:
            logger.critical(
                f"[LOCALES] Translation for key '{key}' and lang '{self.lang}' not found!"
            )
            return "XXX"

        if kwargs:
            try:
                return text.format_map(SafeDict(kwargs))
            except Exception as e:
                logger.error(
                    f"[LOCALES] Error formatting key '{key}': {e}"
                )
                return text

        return text

    def get_unit(self, unit_code: Optional[str]) -> str:
        """Возвращает единицу измерения под язык текущего экземпляра."""
        return get_unit_label(unit_code=unit_code, lang=self.lang)

    def get_currency_symbol(self, currency_code: Optional[str]) -> str:
        """Возвращает символ валюты (например $, ₽, ₿)."""
        return get_currency_symbol(currency_code=currency_code)

    def get_currency(self, currency_code: Optional[str]) -> str:
        """Возвращает локализованное полное название валюты."""
        return get_currency_label(currency_code=currency_code, lang=self.lang)

    def format_order(
        self, order, template_key: str = "user_checkout_confirm", **kwargs
    ) -> str:
        """Универсальный метод форматирования любой карточки заказа / чека."""
        item_lines = []
        items_price = 0.0

        currency_sym = getattr(order, "currency_symbol", None) or "$"

        for item in getattr(order, "items", []):
            product = getattr(item, "product", None)
            product_name = product.name if product else "Deleted Product"
            price = float(getattr(item, "price_at_purchase", 0.0))
            quantity = getattr(item, "quantity", 1)
            item_total = quantity * price
            items_price += item_total

            # Единица измерения
            unit_code = getattr(product, "unit", None) if product else None
            unit_str = self.get_unit(unit_code) if unit_code else ""
            unit_part = f" {unit_str}" if unit_str else ""

            item_lines.append(
                f"• {product_name} — {quantity}{unit_part} x {price:.2f} {currency_sym} = {item_total:.2f} {currency_sym}"
            )

        items_block = "\n".join(item_lines) if item_lines else "—"

        delivery_address = getattr(order, "delivery_address", None)
        address_block = (
            f"📍 {self.get_text('order_delivery_label')} {delivery_address}\n\n"
            if delivery_address
            else ""
        )

        user_comment = getattr(order, "user_comment", None)
        comment_block = (
            f"📝 {self.get_text('order_comment_label')} {user_comment}\n\n"
            if user_comment
            else ""
        )

        total_price = (
            float(order.total_price)
            if getattr(order, "total_price", None) is not None
            else items_price
        )
        delivery_price = float(getattr(order, "delivery_price", 0.0) or 0.0)

        template = self.get_text(template_key)

        context = {
            "id": getattr(order, "id", "N/A"),
            "order_id": getattr(order, "id", "N/A"),
            "items": items_block,
            "address_block": address_block,
            "comment_block": comment_block,
            "items_price": items_price,
            "delivery_price": delivery_price,
            "total_price": total_price,
            "currency": currency_sym,
        }
        context.update(kwargs)

        try:
            return template.format_map(SafeDict(context))
        except Exception as e:
            logger.error(
                f"[LOCALES] Error formatting template '{template_key}': {e}"
            )
            return template

    def format_address(self, maps_url: str) -> str:
        return self.get_text("user_address_link", maps_url=maps_url)