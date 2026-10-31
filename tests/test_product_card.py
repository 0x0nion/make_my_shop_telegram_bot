"""Тесты карточки товара (format_product_from_template).

Описание показывается только если заполнено — без плейсхолдера
«Описание отсутствует» / «No description».
"""
from types import SimpleNamespace

import pytest

from shopcrm_core.locales.locale import Locale
from shopcrm_bot.handlers.client.shop.render_product import format_product_from_template


def _make_product(description=None, name: str = "Tea", price: float = 3.0, unit: str = "pc") -> SimpleNamespace:
    return SimpleNamespace(name=name, price=price, currency="USD", unit=unit, description=description)


@pytest.fixture(autouse=True)
def _reset_locale_cache():
    Locale._cached_locales = None
    yield
    Locale._cached_locales = None


class TestProductCard:
    def test_with_description(self):
        loc = Locale(lang="en")
        text = format_product_from_template(_make_product(description="Great green tea"), loc)
        assert "<b>Tea</b>" in text
        assert "<i>Great green tea</i>" in text
        assert "<b>Price:</b> 3.00 $ / pcs" in text

    def test_without_description_no_placeholder(self):
        """Нет описания — строка просто отсутствует, без плейсхолдера."""
        loc = Locale(lang="en")
        text = format_product_from_template(_make_product(description=None), loc)
        assert "No description" not in text
        assert "<i>" not in text
        assert "<b>Tea</b>" in text
        assert "<b>Price:</b> 3.00 $ / pcs" in text

    def test_empty_description_treated_as_absent(self):
        loc = Locale(lang="en")
        text = format_product_from_template(_make_product(description="   "), loc)
        assert "No description" not in text
        assert "<i>" not in text

    def test_localized_name_used(self):
        loc = Locale(lang="en")
        text = format_product_from_template(_make_product(), loc, name="Green Tea")
        assert "<b>Green Tea</b>" in text
        assert "<b>Tea</b>" not in text

    def test_structure_without_description(self):
        """Карточка без описания: название и цена через одну пустую строку."""
        loc = Locale(lang="en")
        text = format_product_from_template(_make_product(description=None), loc)
        assert text == "<b>Tea</b>\n\n<b>Price:</b> 3.00 $ / pcs"

    def test_structure_with_description(self):
        loc = Locale(lang="en")
        text = format_product_from_template(_make_product(description="Great green tea"), loc)
        assert text == "<b>Tea</b>\n\n<i>Great green tea</i>\n\n<b>Price:</b> 3.00 $ / pcs"
