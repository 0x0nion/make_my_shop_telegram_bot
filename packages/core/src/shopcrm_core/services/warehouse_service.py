# src/services/warehouse_service.py
"""Бизнес-логика управления остатками на складе.

Только реальные товары (не черновики каталога). Остаток определяет видимость
товара для клиента: товар виден, если is_active AND (stock - reserved) > 0.

Модель остатка:
  - ``stock``   — физический остаток на складе;
  - ``reserved``— заморожено активными заказами (бронирование);
  - доступно клиенту = ``stock - reserved``.

Накопительные метрики (отчётность):
  - ``total_arrived``    — всего пришло (пополнения);
  - ``total_written_off``— всего списано вручную;
  - ``total_sold``       — всего продано (по завершённым заказам).

Инвариант: ``stock = initial + total_arrived - total_written_off - total_sold``.
"""
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.repositories.admin_repo import AdminRepository


class WarehouseService:
    """Управление остатками на складе: пополнение, списание, бронирование."""

    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    # --- Ручные операции администратора ---

    async def add_stock(self, product_id: int, qty: int) -> Product | None:
        """Пополнить остаток товара на складе (приход)."""
        return await self.admin_repo.add_stock(product_id, qty)

    async def write_off_stock(self, product_id: int, qty: int) -> Product | None:
        """Списать остаток товара (не ниже 0)."""
        return await self.admin_repo.write_off_stock(product_id, qty)

    # --- Бронирование под заказы ---

    async def reserve_stock(self, product_id: int, qty: int) -> Product | None:
        """Заморозить часть остатка под заказ (создание заказа)."""
        return await self.admin_repo.reserve_stock(product_id, qty)

    async def release_stock(self, product_id: int, qty: int) -> Product | None:
        """Разморозить часть остатка (отмена заказа)."""
        return await self.admin_repo.release_stock(product_id, qty)

    async def confirm_stock(self, product_id: int, qty: int) -> Product | None:
        """Списать товар со склада по завершённому заказу."""
        return await self.admin_repo.confirm_stock(product_id, qty)

    # --- Интеграция с жизненным циклом заказа ---

    async def apply_order_stock(self, order, action: str) -> None:
        """Применить изменение остатка по всем позициям заказа.

        :param order: заказ со списком ``items`` (OrderItem).
        :param action: ``"reserve"`` (создание) | ``"release"`` (отмена)
                       | ``"confirm"`` (завершение).
        """
        handlers = {
            "reserve": self.reserve_stock,
            "release": self.release_stock,
            "confirm": self.confirm_stock,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown stock action: {action!r}")

        for item in getattr(order, "items", []) or []:
            product_id = getattr(item, "product_id", None)
            qty = getattr(item, "quantity", 0) or 0
            if product_id is None or qty <= 0:
                continue
            await handler(product_id, qty)
