"""Тесты форматирования цен (format_price)."""
from decimal import Decimal

from shopcrm_core.utils import format_price


class TestFormatPrice:
    """format_price — strip trailing zeros, без принудительных 2 знаков."""

    def test_whole_number(self):
        assert format_price(100.0) == "100"

    def test_one_decimal(self):
        assert format_price(10.5) == "10.5"

    def test_two_decimals(self):
        assert format_price(10.50) == "10.5"

    def test_crypto_small_value(self):
        assert format_price(0.00000001) == "0.00000001"

    def test_crypto_18_decimals_decimal(self):
        """Decimal сохраняет полную точность 18 знаков."""
        assert format_price(Decimal("0.123456789012345678")) == "0.123456789012345678"

    def test_integer_input(self):
        assert format_price(42) == "42"

    def test_string_input(self):
        assert format_price("10.50") == "10.5"

    def test_decimal_input(self):
        assert format_price(Decimal("0.00000001")) == "0.00000001"

    def test_none_returns_zero(self):
        assert format_price(None) == "0"

    def test_trailing_zeros_stripped(self):
        assert format_price(10.120000) == "10.12"

    def test_large_crypto_value_decimal(self):
        assert format_price(Decimal("1.123456789012345678")) == "1.123456789012345678"

    def test_decimal_whole(self):
        assert format_price(Decimal("100.00")) == "100"
