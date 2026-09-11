"""Тесты сервисной валидации пользовательского ввода."""
from shopcrm_core.locales.locale import Locale
from shopcrm_core.services.validation import (
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
    validate_description,
    validate_name,
    validate_price,
)


class TestValidateName:
    """Валидация названия (категории/товара)."""

    def test_valid_name(self):
        assert validate_name("Кофе", lang="ru") is None

    def test_empty_name_rejected(self):
        error = validate_name("   ", lang="ru")
        assert error is not None
        assert error != "XXX"  # ключ локализован (не заглушка)

    def test_too_long_name_rejected(self):
        error = validate_name("x" * (NAME_MAX_LENGTH + 1), lang="ru")
        assert error is not None

    def test_max_length_name_ok(self):
        assert validate_name("x" * NAME_MAX_LENGTH, lang="ru") is None


class TestValidateDescription:
    """Валидация описания (пустое допустимо)."""

    def test_empty_description_ok(self):
        assert validate_description("", lang="ru") is None

    def test_valid_description(self):
        assert validate_description("Небольшое описание", lang="ru") is None

    def test_too_long_description_rejected(self):
        error = validate_description("x" * (DESCRIPTION_MAX_LENGTH + 1), lang="ru")
        assert error is not None
        assert error != "XXX"


class TestValidatePrice:
    """Валидация цены (положительное число)."""

    def test_valid_price(self):
        price, error = validate_price("10.50", lang="ru")
        assert error is None
        assert price == 10.50

    def test_price_with_comma(self):
        price, error = validate_price("10,50", lang="ru")
        assert error is None
        assert price == 10.50

    def test_zero_price_rejected(self):
        price, error = validate_price("0", lang="ru")
        assert price is None
        assert error is not None

    def test_negative_price_rejected(self):
        price, error = validate_price("-5", lang="ru")
        assert price is None
        assert error is not None

    def test_non_numeric_price_rejected(self):
        price, error = validate_price("abc", lang="ru")
        assert price is None
        assert error is not None
        assert error != "XXX"


class TestLocaleKeysPresent:
    """Новые ключи ошибок присутствуют в locale.json."""

    def test_new_keys_resolve(self):
        Locale.reload_locales()
        locale = Locale(lang="ru")
        for key in (
            "admin.product_editor.invalid_price_value",
            "admin.product_editor.name_required",
            "admin.product_editor.name_too_long",
            "admin.product_editor.desc_too_long",
        ):
            assert locale.get_text(key) != "XXX", f"Ключ '{key}' не найден"
