from enum import Enum


class ProductUnit(str, Enum):
    PIECE = "pc"
    GRAM = "g"
    KILOGRAM = "kg"
    PACK = "pack"
    BUNCH = "bunch"
    LITER = "l"
    MILLILITER = "ml"


UNIT_LABELS: dict[ProductUnit, dict[str, str]] = {
    ProductUnit.PIECE: {"ru": "шт.", "en": "pcs", "es": "un."},
    ProductUnit.GRAM: {"ru": "г", "en": "g", "es": "g"},
    ProductUnit.KILOGRAM: {"ru": "кг", "en": "kg", "es": "kg"},
    ProductUnit.PACK: {"ru": "упк.", "en": "pack", "es": "paq."},
    ProductUnit.BUNCH: {"ru": "пуч.", "en": "bunch", "es": "mazo"},
    ProductUnit.LITER: {"ru": "л", "en": "l", "es": "l"},
    ProductUnit.MILLILITER: {"ru": "мл", "en": "ml", "es": "ml"},
}

DEFAULT_UNIT = ProductUnit.PIECE


def get_unit_label(unit_code: str | None = None, lang: str = "ru") -> str:
    """Безопасно возвращает локализованную метку единицы измерения."""
    if not unit_code:
        unit_code = DEFAULT_UNIT.value
    try:
        unit_enum = ProductUnit(unit_code)
        labels = UNIT_LABELS[unit_enum]
        return labels.get(lang) or labels.get("en") or labels.get("ru") or str(unit_code)
    except ValueError:
        return str(unit_code)