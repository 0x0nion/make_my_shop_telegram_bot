"""Тесты форматирования цен (format_price)."""
from decimal import Decimal

from shopcrm_core.utils import format_price


class TestFormatPrice:
    """format_price — минимум 2 знака после точки, без потери точности."""

    def test_whole_number(self):
        assert format_price(100.0) == "100.00"

    def test_one_decimal(self):
        assert format_price(10.5) == "10.50"

    def test_two_decimals(self):
        assert format_price(10.50) == "10.50"

    def test_crypto_small_value(self):
        assert format_price(0.00000001) == "0.00000001"

    def test_crypto_tiny_value(self):
        """Маленький валидный дробный ценник остаётся видимым."""
        assert format_price(0.000004) == "0.000004"

    def test_three_decimals_preserved(self):
        assert format_price(10.123) == "10.123"

    def test_crypto_18_decimals_decimal(self):
        """Decimal сохраняет полную точность 18 знаков."""
        assert format_price(Decimal("0.123456789012345678")) == "0.123456789012345678"

    def test_integer_input(self):
        assert format_price(42) == "42.00"

    def test_string_input(self):
        assert format_price("10.50") == "10.50"

    def test_decimal_input(self):
        assert format_price(Decimal("0.00000001")) == "0.00000001"

    def test_none_returns_zero(self):
        assert format_price(None) == "0.00"

    def test_zero(self):
        assert format_price(0.0) == "0.00"

    def test_trailing_zeros_stripped(self):
        assert format_price(10.120000) == "10.12"

    def test_large_crypto_value_decimal(self):
        assert format_price(Decimal("1.123456789012345678")) == "1.123456789012345678"

    def test_decimal_whole(self):
        assert format_price(Decimal("100.00")) == "100.00"

    def test_db_value_with_trailing_zeros(self):
        """Numeric(28, 18) из БД: 18 хвостовых нулей не показываются."""
        assert format_price(Decimal("10.000000000000000000")) == "10.00"

