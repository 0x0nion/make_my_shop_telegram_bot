"""Тесты локализации: покрытие ключей, fallback, форматирование."""
import json
from pathlib import Path

import pytest

from shopcrm_core.locales.currencies import (
    DEFAULT_CURRENCY,
    get_currency_label,
    get_currency_symbol,
)
from shopcrm_core.locales.locale import Locale
from shopcrm_core.locales.utils import SafeDict
from shopcrm_core.locales.units import get_unit_label, ProductUnit, DEFAULT_UNIT

LOCALE_PATH = Path(__file__).resolve().parent.parent / "packages" / "core" / "src" / "shopcrm_core" / "locales" / "locale.json"
SUPPORTED_LANGS = ("ru", "en", "es")


def _load_raw_locales() -> dict:
    with open(LOCALE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_text_paths(data: dict, prefix: str = "") -> list[str]:
    """Рекурсивно собирает все пути до словарей с языковыми ключами."""
    paths = []
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            # Если все значения — строки, это локализованный текст
            if all(isinstance(v, str) for v in value.values()) and value:
                paths.append(full)
            else:
                paths.extend(_collect_text_paths(value, full))
    return paths


class TestLocaleCoverage:
    """Каждый текстовый ключ должен существовать во всех трёх языках."""

    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        Locale._cached_locales = None
        yield
        Locale._cached_locales = None

    def test_all_keys_have_all_languages(self):
        """Каждый текстовый путь содержит ru, en, es."""
        raw = _load_raw_locales()
        text_paths = _collect_text_paths(raw)
        assert len(text_paths) > 0, "Не найдено ни одного текстового ключа"

        missing = []
        for path in text_paths:
            keys = path.split(".")
            node = raw
            for k in keys:
                node = node[k]
            for lang in SUPPORTED_LANGS:
                if lang not in node:
                    missing.append(f"{path} → {lang}")

        assert not missing, f"Отсутствующие языки: {missing[:10]}"

    def test_get_text_returns_localized_string(self):
        """get_text возвращает строку на запрошенном языке."""
        loc = Locale(lang="ru")
        text = loc.get_text("text.client.user_main")
        assert isinstance(text, str)
        assert text != "XXX"

    def test_get_text_fallback_to_ru(self):
        """Если язык не найден — fallback на ru."""
        # Создаём локаль с несуществующим языком
        loc = Locale(lang="fr")
        # Должен вернуться ru-вариант (fallback chain: lang → ru → en)
        text = loc.get_text("text.client.user_main")
        assert isinstance(text, str)
        assert text != "XXX"

    def test_get_text_with_kwargs(self):
        """get_text поддерживает форматирование с параметрами."""
        loc = Locale(lang="en")
        text = loc.get_text("text.admin.catalog.category_title", name="Fruits")
        assert "Fruits" in text

    def test_get_text_missing_path_returns_xxx(self):
        """Несуществующий путь → 'XXX'."""
        loc = Locale(lang="en")
        text = loc.get_text("text.nonexistent.key.here")
        assert text == "XXX"

    def test_get_text_short_path_autoprefix(self):
        """Короткий путь без 'text.' получает авто-префикс."""
        loc = Locale(lang="en")
        # "client.user_main" → "text.client.user_main"
        text = loc.get_text("client.user_main")
        assert isinstance(text, str)
        assert text != "XXX"


class TestSafeDict:
    """SafeDict не падает на неизвестных ключах."""

    def test_known_key(self):
        d = SafeDict(name="World")
        assert "{name}".format_map(d) == "World"

    def test_missing_key_returns_placeholder(self):
        d = SafeDict()
        assert "{unknown}".format_map(d) == "{unknown}"

    def test_mixed_keys(self):
        d = SafeDict(a="1")
        assert "{a} {b}".format_map(d) == "1 {b}"


class TestUnits:
    """get_unit_label: корректные метки единиц измерения."""

    def test_default_unit(self):
        assert get_unit_label(None, "ru") == "шт."
        assert get_unit_label(None, "en") == "pcs"

    def test_all_units_ru(self):
        expected = {
            "pc": "шт.", "g": "г", "kg": "кг",
            "pack": "упк.", "bunch": "пуч.", "l": "л", "ml": "мл",
        }
        for code, label in expected.items():
            assert get_unit_label(code, "ru") == label

    def test_unknown_unit_returns_code(self):
        assert get_unit_label("unknown_unit", "ru") == "unknown_unit"

    def test_locale_get_unit(self):
        loc = Locale(lang="ru")
        assert loc.get_unit("kg") == "кг"
        assert loc.get_unit(None) == "шт."


class TestCurrencies:
    """Валюты: символы, локализованные метки, fallback на невалидные коды."""

    def test_symbol_for_known_currencies(self):
        assert get_currency_symbol("USD") == "$"
        assert get_currency_symbol("RUB") == "₽"
        assert get_currency_symbol("BTC") == "₿"

    def test_symbol_default_when_none(self):
        assert get_currency_symbol(None) == "$"
        assert get_currency_symbol("") == "$"

    def test_symbol_unknown_code_returns_code(self):
        assert get_currency_symbol("EUR") == "EUR"

    def test_label_localized(self):
        assert get_currency_label("RUB", "ru") == "Рубль (₽)"
        assert get_currency_label("RUB", "en") == "Ruble (₽)"

    def test_label_default_currency(self):
        assert get_currency_label() == "Доллар ($)"
        assert get_currency_label("USD", "ru") == "Доллар ($)"

    def test_label_unknown_code_returns_code(self):
        """Регрессия: невалидный код не должен падать с NameError."""
        assert get_currency_label("EUR", "ru") == "EUR"
        assert get_currency_label("EUR", "en") == "EUR"

    def test_default_currency_is_usd(self):
        assert DEFAULT_CURRENCY.value == "USD"
