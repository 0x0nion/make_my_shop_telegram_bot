# src/core/constants.py
from enum import Enum


class OrderStatus(str, Enum):
    """Жизненный цикл заказа."""
    PENDING = "pending"                             # Создан / ожидает действий
    PAYMENT_REQUESTED = "payment_requested"         # Админ запросил оплату у клиента
    AWAITING_CONFIRMATION = "awaiting_confirmation" # Чек/хэш отправлен, ждет проверки
    PROCESSING = "processing"                       # Подтвержден админом / готовится к отправке
    DELIVERING = "delivering"                       # Взята курьером / в пути
    COMPLETED = "completed"                         # Завершен
    CANCELLED = "cancelled"                         # Отменен

    @classmethod
    def is_final(cls, status: str) -> bool:
        """Завершен ли заказ окончательно (успешно или с ошибкой)."""
        return status in (cls.COMPLETED.value, cls.CANCELLED.value)

    @classmethod
    def is_cancellable_by_client(cls, status: str) -> bool:
        """Может ли клиент отменить заказ самостоятельно (пока он не передан курьеру)."""
        return status in (
            cls.PENDING.value,
            cls.PAYMENT_REQUESTED.value,
            cls.AWAITING_CONFIRMATION.value,
            cls.PROCESSING.value,
        )


# Единый источник истины для фильтров меню админ-ордеров:
# callback-ключ кнопки -> значение статуса в БД.
# Порядок ключей определяет порядок кнопок в меню (жизненный цикл заказа).
ADMIN_ORDER_STATUS_FILTERS: dict[str, str] = {
    "admin_order_pending": OrderStatus.PENDING.value,
    "admin_order_payment_requested": OrderStatus.PAYMENT_REQUESTED.value,
    "admin_order_awaiting": OrderStatus.AWAITING_CONFIRMATION.value,
    "admin_order_processing": OrderStatus.PROCESSING.value,
    "admin_order_delivering": OrderStatus.DELIVERING.value,
    "admin_order_completed": OrderStatus.COMPLETED.value,
    "admin_order_cancelled": OrderStatus.CANCELLED.value,
}

# Множество всех допустимых статусов заказа (генерируется из enum).
# Используется для валидации кнопок меню «Изменить статус»:
# ключи кнопок в locale.json совпадают со значениями статусов.
ORDER_STATUS_VALUES: frozenset[str] = frozenset(s.value for s in OrderStatus)

# Короткие коды статусов для callback_data (лимит Telegram — 64 байта).
# Применяются там, где в callback попадают полные имена статусов
# (например, admin_order_set_status / admin_order_close_confirm),
# чтобы не превысить лимит при длинных статусах (awaiting_confirmation).
ORDER_STATUS_CODES: dict[str, str] = {
    OrderStatus.PENDING.value: "1",
    OrderStatus.PAYMENT_REQUESTED.value: "2",
    OrderStatus.AWAITING_CONFIRMATION.value: "3",
    OrderStatus.PROCESSING.value: "4",
    OrderStatus.DELIVERING.value: "5",
    OrderStatus.COMPLETED.value: "6",
    OrderStatus.CANCELLED.value: "7",
}
# Обратное отображение: код -> полное имя статуса.
ORDER_STATUS_BY_CODE: dict[str, str] = {v: k for k, v in ORDER_STATUS_CODES.items()}


class PaymentProofType(str, Enum):
    """Типы подтверждения оплаты."""
    CASH = "cash"
    PHOTO = "photo"
    DOCUMENT = "document"
    TX_HASH = "tx_hash"