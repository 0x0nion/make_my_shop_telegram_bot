"""Тесты публичного API метаданных БД (для миграций консьюмеров)."""
from shopcrm_core.db import Base, get_metadata

# Ожидаемые таблицы core (11 шт.).
EXPECTED_TABLES = {
    "users",
    "categories",
    "products",
    "cart_items",
    "orders",
    "order_items",
    "locale_texts",
    "templates",
    "temp_categories",
    "temp_products",
    "temp_locale_texts",
}


class TestMetadataApi:
    """get_metadata() отдаёт Base.metadata со всеми таблицами core."""

    def test_returns_base_metadata(self):
        """Возвращаемый объект — это Base.metadata."""
        assert get_metadata() is Base.metadata

    def test_all_expected_tables_present(self):
        """Все ожидаемые таблицы зарегистрированы в метаданных."""
        tables = set(get_metadata().tables.keys())
        missing = EXPECTED_TABLES - tables
        assert not missing, f"Отсутствуют таблицы: {sorted(missing)}"

    def test_table_count(self):
        """Точное количество таблиц совпадает с ожидаемым."""
        assert len(get_metadata().tables) == len(EXPECTED_TABLES)

    def test_each_table_has_columns(self):
        """Каждая ожидаемая таблица имеет колонки."""
        for name in EXPECTED_TABLES:
            table = get_metadata().tables[name]
            assert table.columns, f"Таблица '{name}' без колонок"
