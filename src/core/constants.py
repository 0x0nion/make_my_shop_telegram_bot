# src/core/constants.py
from enum import Enum


class OrderStatus(str, Enum):
    """Жизненный цикл заказа."""
    PENDING = "pending"                             # Создан / ожидает действий
    AWAITING_CONFIRMATION = "awaiting_confirmation" # Чек/хэш отправлен, ждет проверки
    PROCESSING = "processing"                       # Подтвержден админом / готовится к отправке
    DELIVERING = "delivering"                       # Взята курьером / в пути
    COMPLETED = "completed"                         # Завершен
    CANCELLED = "cancelled"                         # Отменен

    @classmethod
    def is_final(cls, status: str) -> bool:
        """Завершен ли заказ окончательно (успешно или с ошибкой)."""
        return status in (cls.COMPLETED.value, cls.CANCELLED.value)


class PaymentProofType(str, Enum):
    """Типы подтверждения оплаты."""
    CASH = "cash"
    PHOTO = "photo"
    DOCUMENT = "document"
    TX_HASH = "tx_hash"