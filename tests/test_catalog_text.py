"""Тесты текста каталога (build_catalog_text).

Компактный нумерованный список товаров «как в составе заказа»:
без разделительных линий, без пустых строк между позициями,
описание категории показывается только если заполнено.
"""
from types import SimpleNamespace

import pytest

from shopcrm_core.locales.locale import Locale
from shopcrm_bot.ui.presenters.catalog import build_catalog_text


def _make_product(name: str = "Tea", price: float = 3.0, unit: str = "pc", pid: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=pid, name=name, price=price, currency="USD", unit=unit)


@pytest.fixture(autouse=True)
def _reset_locale_cache():
    Locale._cached_locales = None
    yield
    Locale._cached_locales = None


class TestCatalogText:
    def test_no_separator_lines(self):
        """В тексте каталога нет линий-разделителей ─."""
        loc = Locale(lang="en")
        text = build_catalog_text(
            locale=loc, title="Shop", description="Desc", products=[_make_product()]
        )
        assert "─" not in text

    def test_numbered_compact_list(self):
        """Позиции нумерованы и склеены без пустых строк между ними."""
        loc = Locale(lang="en")
        products = [_make_product("Tea", 3.0, pid=1), _make_product("Coffee", 5.5, pid=2)]
        text = build_catalog_text(locale=loc, title="Shop", description="", products=products)
        assert "1. <b>Tea</b>" in text
        assert "2. <b>Coffee</b>" in text
        assert "1. <b>Tea</b> — 3.00 $ / pcs\n2. <b>Coffee</b> — 5.50 $ / pcs" in text

    def test_products_header_present(self):
        loc = Locale(lang="en")
        text = build_catalog_text(locale=loc, title="Shop", description="", products=[_make_product()])
        assert "🛒 <b>Products:</b>" in text

    def test_footer_present(self):
        loc = Locale(lang="en")
        text = build_catalog_text(locale=loc, title="Shop", description="", products=[_make_product()])
        assert "ℹ️ Select a category or product." in text

    def test_description_shown_when_present(self):
        loc = Locale(lang="en")
        text = build_catalog_text(
            locale=loc, title="Shop", description="Best goods", products=[_make_product()]
        )
        assert "Best goods" in text

    def test_description_skipped_when_empty(self):
        """Пустое описание пропускается — без плейсхолдера и лишних пустых строк."""
        loc = Locale(lang="en")
        text = build_catalog_text(locale=loc, title="Shop", description="", products=[])
        assert text == "Shop"

    def test_whitespace_description_skipped(self):
        loc = Locale(lang="en")
        text = build_catalog_text(locale=loc, title="Shop", description="   ", products=[])
        assert text == "Shop"

    def test_no_products_title_only(self):
        """Без товаров список и футер не добавляются."""
        loc = Locale(lang="en")
        text = build_catalog_text(locale=loc, title="Shop", description="Desc", products=[])
        assert text == "Shop\n\nDesc"
        assert "Products" not in text

    def test_localized_product_names(self):
        loc = Locale(lang="en")
        products = [_make_product("Tea", pid=1)]
        text = build_catalog_text(
            locale=loc, title="Shop", description="", products=products, product_names={1: "Green Tea"}
        )
        assert "<b>Green Tea</b>" in text
        assert "<b>Tea</b>" not in text

    def test_unit_from_product(self):
        loc = Locale(lang="en")
        text = build_catalog_text(
            locale=loc, title="Shop", description="", products=[_make_product(unit="pack")]
        )
        assert "/ pack" in text
