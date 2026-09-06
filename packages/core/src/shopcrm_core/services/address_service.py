# src/services/address_service.py
"""Бизнес-логика нормализации адреса доставки.

Определяет, в каком виде хранить адрес (сырое значение) и его тип
("location" | "text"), чтобы отображение (ссылка на карту / текст)
было единообразным для клиента и администратора.
"""

ADDRESS_TYPE_LOCATION = "location"
ADDRESS_TYPE_TEXT = "text"

_GOOGLE_MAPS_URL_TEMPLATE = (
    "https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
)


def build_location_address(latitude: float, longitude: float) -> tuple[str, str]:
    """Возвращает (значение, тип) для адреса-локации: ссылка на Google Maps."""
    url = _GOOGLE_MAPS_URL_TEMPLATE.format(latitude=latitude, longitude=longitude)
    return url, ADDRESS_TYPE_LOCATION


def normalize_text_address(text: str | None) -> tuple[str, str]:
    """Возвращает (значение, тип) для текстового ввода.

    Ссылка (http/https) трактуется как location, остальное — как text.
    """
    value = (text or "").strip()
    addr_type = (
        ADDRESS_TYPE_LOCATION
        if value.lower().startswith(("http://", "https://"))
        else ADDRESS_TYPE_TEXT
    )
    return value, addr_type
