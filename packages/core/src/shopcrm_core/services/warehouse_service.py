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
import logging

from shopcrm_core.db.models.product import Product
from shopcrm_core.db.repositories.admin_repo import AdminRepository

logger = logging.getLogger(__name__)


class WarehouseService:
    """Управление остатками на складе: пополнение, списание, бронирование."""

    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    # --- Ручные операции администратора ---

    async def add_stock(
            self, product_id: int, qty: int, admin_id: int | None = None, comment: str | None = None
    ) -> Product | None:
        """Пополнить остаток товара на складе (приход).

        :param admin_id: Telegram ID администратора (фиксируется в журнале).
        :param comment: комментарий/причина движения (фиксируется в журнале).
        """
        return await self.admin_repo.add_stock(product_id, qty, admin_id=admin_id, comment=comment)

    async def write_off_stock(
            self, product_id: int, qty: int, admin_id: int | None = None, comment: str | None = None
    ) -> Product | None:
        """Списать остаток товара (не ниже 0).

        :param admin_id: Telegram ID администратора (фиксируется в журнале).
        :param comment: комментарий/причина движения (фиксируется в журнале).
        """
        return await self.admin_repo.write_off_stock(product_id, qty, admin_id=admin_id, comment=comment)

    # --- Полное удаление товара (очистка архива) ---

    async def delete_product(
            self, product_id: int, admin_id: int | None = None
    ) -> tuple[Product | None, str | None]:
        """Полностью удалить товар со склада вместе с историей.

        Удаляет товар, его журнал движений, локали и позиции в корзинах
        (CASCADE); в заказах ссылка на товар обнуляется (SET NULL).
        Операция необратима — предназначена для очистки архива.

        Блокируется, если у товара есть остаток (``stock > 0``) или активные
        заказы (``reserved > 0``) — сначала нужно списать остаток / дождаться
        завершения заказов.

        :param admin_id: Telegram ID администратора (фиксируется в логе).
        :return: ``(product, error)`` — ``error`` равен ``"not_found"`` /
                 ``"has_stock"`` / ``"has_orders"`` при отказе или ``None``
                 при успехе.
        """
        product = await self.admin_repo.get_product_by_id(product_id)
        if not product:
            return None, "not_found"
        if (product.stock or 0) > 0:
            logger.info(
                f"Delete product blocked: product_id={product_id} "
                f"admin_id={admin_id} reason=has_stock stock={product.stock}"
            )
            return product, "has_stock"
        if (product.reserved or 0) > 0:
            logger.info(
                f"Delete product blocked: product_id={product_id} "
                f"admin_id={admin_id} reason=has_orders reserved={product.reserved}"
            )
            return product, "has_orders"

        name = product.name
        await self.admin_repo.delete_product(product_id, use_temp=False, admin_id=admin_id)
        logger.info(
            f"Product fully deleted: product_id={product_id} name={name!r} "
            f"admin_id={admin_id}"
        )
        return product, None

    # --- Возврат из архива в каталог ---

    async def restore_product(
            self, product_id: int, admin_id: int | None = None
    ) -> tuple[Product | None, str | None]:
        """Вернуть архивный товар в каталог (``is_active=True``).

        Товар снова становится видимым в магазине и попадает в черновик
        каталога при следующем открытии редактора (``sync_to_temp``).
        Остаток, журнал движений и заказы не затрагиваются.

        :param admin_id: Telegram ID администратора (фиксируется в логе).
        :return: ``(product, error)`` — ``error`` равен ``"not_found"`` /
                 ``"already_active"`` при отказе или ``None`` при успехе.
        """
        product = await self.admin_repo.get_product_by_id(product_id)
        if not product:
            return None, "not_found"
        if product.is_active:
            return product, "already_active"

        await self.admin_repo.update_product_field(product_id, "is_active", True)
        logger.info(
            f"Product restored to catalog: product_id={product_id} "
            f"name={product.name!r} admin_id={admin_id}"
        )
        return await self.admin_repo.get_product_by_id(product_id), None

    # --- Бронирование под заказы ---

    async def reserve_stock(
            self, product_id: int, qty: int, order_id: int | None = None
    ) -> Product | None:
        """Заморозить часть остатка под заказ (создание заказа).

        :param order_id: ID заказа (фиксируется в журнале).
        """
        return await self.admin_repo.reserve_stock(product_id, qty, order_id=order_id)

    async def release_stock(
            self, product_id: int, qty: int, order_id: int | None = None
    ) -> Product | None:
        """Разморозить часть остатка (отмена заказа).

        :param order_id: ID заказа (фиксируется в журнале).
        """
        return await self.admin_repo.release_stock(product_id, qty, order_id=order_id)

    async def confirm_stock(
            self, product_id: int, qty: int, order_id: int | None = None
    ) -> Product | None:
        """Списать товар со склада по завершённому заказу.

        :param order_id: ID заказа (фиксируется в журнале).
        """
        return await self.admin_repo.confirm_stock(product_id, qty, order_id=order_id)

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

        order_id = getattr(order, "id", None)
        for item in getattr(order, "items", []) or []:
            product_id = getattr(item, "product_id", None)
            qty = getattr(item, "quantity", 0) or 0
            if product_id is None or qty <= 0:
                continue
            await handler(product_id, qty, order_id=order_id)
