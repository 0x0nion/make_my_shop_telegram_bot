from enum import Enum


class Currency(str, Enum):
    USD = "USD"
    USDT = "USDT"
    BTC = "BTC"
    ARS = "ARS"
    RUB = "RUB"


DEFAULT_CURRENCY = Currency.USD

CURRENCY_DATA: dict[Currency, dict[str, str]] = {
    Currency.USD: {
        "symbol": "$",
        "ru": "Доллар ($)",
        "en": "US Dollar ($)",
        "es": "Dólar ($)",
    },
    Currency.USDT: {
        "symbol": "USDT",
        "ru": "USDT",
        "en": "USDT",
        "es": "USDT",
    },
    Currency.BTC: {
        "symbol": "₿",
        "ru": "Bitcoin (₿)",
        "en": "Bitcoin (₿)",
        "es": "Bitcoin (₿)",
    },
    Currency.ARS: {
        "symbol": "ARS$",
        "ru": "Песо ($)",
        "en": "Peso ($)",
        "es": "Peso ($)",
    },
    Currency.RUB: {
        "symbol": "₽",
        "ru": "Рубль (₽)",
        "en": "Ruble (₽)",
        "es": "Rublo (₽)",
    },
}


def get_currency_symbol(currency_code: str | None = None) -> str:
    """Возвращает символ валюты (например, '$', '₽', '₿')."""
    if not currency_code:
        return CURRENCY_DATA[DEFAULT_CURRENCY]["symbol"]
    try:
        curr_enum = Currency(currency_code)
        return CURRENCY_DATA.get(curr_enum, {}).get("symbol", currency_code)
    except ValueError:
        return currency_code


def get_currency_label(
    currency_code: str | None = None, lang: str = "ru"
) -> str:
    """Возвращает локализованное название валюты."""
    code = currency_code or DEFAULT_CURRENCY.value
    try:
        curr_enum = Currency(code)
        labels = CURRENCY_DATA.get(curr_enum, {})
        return labels.get(lang) or labels.get("en") or labels.get("ru") or code
    except ValueError:
        return code