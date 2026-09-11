# locales/locale.py
import html
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from shopcrm_core.locales.utils import SafeDict

logger = logging.getLogger(__name__)


class Locale:
    """Единый локаль-менеджер.

    Все тексты (клиентские, админские, кнопки, валюты, единицы) хранятся
    в едином файле locales/locale.json и читаются через него.
    """

    locale_path = Path(__file__).resolve().parent / "locale.json"
    _cached_locales: Optional[Dict[str, Any]] = None

    def __init__(self, lang: str = "en"):
        self.lang = lang or "en"
        self.locales: Dict[str, Any] = self._get_locales()

    @classmethod
    def _get_locales(cls) -> Dict[str, Any]:
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

    # --- Вспомогательные методы ---

    def _resolve_path(self, path: str, silent: bool = False) -> Optional[Any]:
        keys = path.split(".")
        current: Any = self.locales

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                if not silent:
                    logger.critical(
                        f"[LOCALES] Path '{path}' (segment '{k}') not found in locale.json!"
                    )
                return None

        return current

    def _get_localized_value(
        self, path: str, silent: bool = False
    ) -> Optional[Union[str, Dict[str, Any], list]]:
        data = self._resolve_path(path, silent=silent)

        if data is None:
            return None

        if isinstance(data, dict):
            value = data.get(self.lang) or data.get("ru") or data.get("en")
            if value is not None:
                return value

        return data

    # --- Публичные методы получения текста и сырых данных клавиатур ---

    def get_text(self, path: str, **kwargs) -> str:
        """Возвращает локализованный текст.

        Принимает пути в видах:
          - "text.client.user_main" (полный путь)
          - "client.user_main" (с авто-префиксом "text.")
          - "user_main" (корневой клиентский ключ, как в старом msg.json)
        """
        if path.startswith("text."):
            target_path = path
        elif self._resolve_path(path, silent=True) is not None:
            target_path = path
        else:
            target_path = f"text.{path}"

        text = self._get_localized_value(target_path)

        if text is None or not isinstance(text, str):
            logger.critical(
                f"[LOCALES] Text translation for path '{target_path}' and lang '{self.lang}' invalid or not found!"
            )
            return "XXX"

        if kwargs:
            try:
                return text.format_map(SafeDict(kwargs))
            except Exception as e:
                logger.error(f"[LOCALES] Error formatting path '{target_path}': {e}")
                return text

        return text

    def has_text(self, path: str) -> bool:
        """True, если по пути существует валидный перевод для текущего языка."""
        if path.startswith("text."):
            target_path = path
        elif self._resolve_path(path, silent=True) is not None:
            target_path = path
        else:
            target_path = f"text.{path}"

        value = self._get_localized_value(target_path, silent=True)
        return isinstance(value, str) and value != ""

    def get_keyboard_data(self, path: str) -> Optional[Union[Dict[str, Any], list]]:
        """Возвращает сырые данные из массива keyboards в locale.json."""
        target_path = path if path.startswith("keyboards.") else f"keyboards.{path}"
        return self._get_localized_value(target_path)

    def get_order_status_label(self, status: Optional[str]) -> str:
        """Локализованная подпись статуса заказа (из keyboards.order_status_menu).

        Fallback — исходное значение статуса.
        """
        if not status:
            return "—"
        buttons = (self.get_keyboard_data("admin.order_status_menu") or {}).get("buttons", {})
        label = buttons.get(status)
        if isinstance(label, dict):
            return label.get(self.lang) or label.get("ru") or label.get("en") or str(status)
        return str(status)

    # --- Валюты и Единицы (из единого locale.json) ---

    def get_unit(self, unit_code: Optional[str]) -> str:
        code = unit_code or self.locales.get("units", {}).get("default", "pc")
        data = self.locales.get("units", {}).get(code)
        if isinstance(data, dict):
            return data.get(self.lang) or data.get("ru") or data.get("en") or code
        return str(code)

    def get_currency_symbol(self, currency_code: Optional[str] = None) -> str:
        code = currency_code or self.locales.get("currencies", {}).get("default", "USD")
        data = self.locales.get("currencies", {}).get(code)
        if isinstance(data, dict):
            return data.get("symbol", code)
        return code

    def get_currency(self, currency_code: Optional[str]) -> str:
        code = currency_code or self.locales.get("currencies", {}).get("default", "USD")
        data = self.locales.get("currencies", {}).get(code)
        if isinstance(data, dict):
            return (
                data.get(self.lang)
                or data.get("ru")
                or data.get("en")
                or data.get("symbol", code)
            )
        return code

    # --- Форматирование заказов ---

    def format_order(
        self, order, template_key: str = "client.user_checkout_confirm", **kwargs
    ) -> str:
        """Универсальный метод форматирования любой карточки заказа / чека.

        template_key принимает как полный путь ("client.user_checkout_confirm"),
        так и корневой ключ ("user_checkout_confirm").
        """
        item_lines = []
        items_price = 0.0

        currency_sym = getattr(order, "currency_symbol", None) or self.get_currency_symbol()

        for idx, item in enumerate(getattr(order, "items", []) or [], start=1):
            product = getattr(item, "product", None)
            product_name = product.name if product else self.get_text(
                "admin.orders.deleted_product", product_id=getattr(item, "product_id", "?")
            )
            price = float(getattr(item, "price_at_purchase", 0.0) or 0.0)
            quantity = int(getattr(item, "quantity", 1) or 1)
            item_total = quantity * price
            items_price += item_total

            unit_str = (
                self.get_unit(getattr(product, "unit", None))
                if product
                else self.get_text("admin.orders.unit_default")
            )

            item_lines.append(
                self.get_text(
                    "admin.orders.item_line",
                    idx=idx, name=product_name, qty=quantity, unit=unit_str,
                    price=price, currency=currency_sym, sum=item_total,
                )
            )

        items_block = "\n".join(item_lines) if item_lines else "—"

        delivery_address = getattr(order, "delivery_address", None)
        delivery_address_type = getattr(order, "delivery_address_type", None)
        address_block = (
            f"📍 {self.get_text('client.order_delivery_label')} {self.format_address(delivery_address, delivery_address_type)}\n\n"
            if delivery_address
            else ""
        )

        user_comment = getattr(order, "user_comment", None)
        comment_block = (
            f"📝 {self.get_text('client.order_comment_label')} {user_comment}\n\n"
            if user_comment
            else ""
        )

        total_price = (
            float(order.total_price)
            if getattr(order, "total_price", None) is not None
            else items_price
        )
        delivery_price = float(getattr(order, "delivery_price", 0.0) or 0.0)

        not_specified = self.get_text("client.order_not_specified")
        address = self.format_address(delivery_address, delivery_address_type) or not_specified
        comment = user_comment or not_specified

        created_at = getattr(order, "created_at", None)
        created_at_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "—"

        template = self.get_text(template_key)

        context = {
            "id": getattr(order, "id", "N/A"),
            "order_id": getattr(order, "id", "N/A"),
            "items": items_block,
            "address_block": address_block,
            "comment_block": comment_block,
            "address": address,
            "comment": comment,
            "created_at": created_at_str,
            "status": self.get_order_status_label(getattr(order, "status", None)),
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

    def format_address(self, value: str | None, addr_type: str | None = None) -> str:
        """Форматирует адрес для вывода: location → ссылка на карту, text → как есть (с экранированием)."""
        if not value:
            return ""
        value = value.strip()
        if addr_type == "location":
            return self.get_text("client.user_address_link", maps_url=value)
        return html.escape(value)