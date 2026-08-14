# keyboards/user_inline.py
import json
import logging
from pathlib import Path
from typing import Optional
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


class UserInlineKb:
    # Ищем JSON-файл прямо в той же папке keyboards/ рядом с текущим файлом
    locale_path = Path(__file__).resolve().parent / "user_kb.json"

    def __init__(self, lang: str = "ru"):
        self.lang = lang
        self.template = self._load_json()

    def _load_json(self) -> dict:
        """Загружает JSON-файл с переводами из папки keyboards/."""
        if not self.locale_path.exists():
            # Запасная проверка на случай, если файл называется kb.json
            fallback_path = Path(__file__).resolve().parent / "kb.json"
            if fallback_path.exists():
                self.locale_path = fallback_path
            else:
                logger.error(f"[USER KB] Файл локализации не найден: {self.locale_path}")
                return {}

        try:
            with open(self.locale_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            logger.critical(f"[USER KB] Ошибка чтения {self.locale_path}: {e}", exc_info=True)
            return {}

    def get_text(self, path: str, default: str = "") -> str:
        """
        Рекурсивно извлекает локализованную строку по пути вида 'order_payment_request.text'.
        """
        if not self.template:
            return default

        keys = path.split(".")
        current = self.template

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, {})
            else:
                return default

        # Если дошли до словаря языков {"ru": "...", "en": "..."}
        if isinstance(current, dict):
            return current.get(self.lang) or current.get("ru") or current.get("en") or default

        if isinstance(current, str):
            return current

        return default

    def get_order_payment_request_kb(self, order_id: int) -> InlineKeyboardMarkup:
        """Генерирует клавиатуру выбора способа оплаты для клиента."""
        builder = InlineKeyboardBuilder()

        cash_text = self.get_text(
            "order_payment_request.buttons.cash",
            "💵 Наличными (курьеру)"
        )
        paid_text = self.get_text(
            "order_payment_request.buttons.paid",
            "✅ Я оплатил"
        )

        builder.button(
            text=cash_text,
            callback_data=f"user_pay_cash:{order_id}"
        )
        builder.button(
            text=paid_text,
            callback_data=f"user_pay_confirm:{order_id}"
        )

        builder.adjust(1)
        return builder.as_markup()