"""Валидация пользовательского ввода на сервисном уровне.

Чистые функции без зависимостей от Telegram/aiogram: принимают значение и
язык, возвращают локализованное сообщение об ошибке (или None, если ввод
корректен). Хэндлеры только отображают результат — правила живут здесь.
"""
from typing import Optional, Tuple

from shopcrm_core.locales.locale import Locale

# Ограничения по длине строк (единый источник правды).
NAME_MAX_LENGTH = 30
DESCRIPTION_MAX_LENGTH = 500


def _t(lang: str, path: str, **kwargs) -> str:
    """Локализованный текст по пути (авто-префикс "text.")."""
    return Locale(lang=lang).get_text(path, **kwargs)


def validate_name(
    value: str, lang: str, max_length: int = NAME_MAX_LENGTH
) -> Optional[str]:
    """Валидирует название (категории/товара).

    :return: локализованное сообщение об ошибке или None, если корректно.
    """
    text = (value or "").strip()
    if not text:
        return _t(lang, "admin.product_editor.name_required")
    if len(text) > max_length:
        return _t(lang, "admin.product_editor.name_too_long", max=max_length)
    return None


def validate_description(
    value: str, lang: str, max_length: int = DESCRIPTION_MAX_LENGTH
) -> Optional[str]:
    """Валидирует описание (пустое значение допустимо).

    :return: локализованное сообщение об ошибке или None, если корректно.
    """
    text = value or ""
    if len(text) > max_length:
        return _t(lang, "admin.product_editor.desc_too_long", max=max_length)
    return None


def validate_price(value: str, lang: str) -> Tuple[Optional[float], Optional[str]]:
    """Парсит и валидирует цену.

    :return: (price, error). price — float или None; error — локализованная
             ошибка или None.
    """
    clean = (value or "").strip().replace(",", ".", 1)
    try:
        price = float(clean)
    except (ValueError, TypeError):
        return None, _t(lang, "admin.product_editor.invalid_price_value")
    if price <= 0:
        return None, _t(lang, "admin.product_editor.invalid_price_value")
    return price, None
