"""Тесты управления остатками на складе и лимитов корзины.

Проверяют:
  - видимость товара для клиента (is_active AND stock > 0)
  - лимиты корзины (нельзя заказать больше остатка)
  - пополнение/списание остатка (floor 0)
  - валидацию количества
  - журнал складских движений (stock_movements)
"""
import pytest_asyncio
from shopcrm_core.constants import StockMovementType
from shopcrm_core.db.models.order import Order, OrderItem
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.models.stock_movement import StockMovement
from shopcrm_core.db.models.temp_models import TempProduct
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.db.repositories.shop_repo import ShopRepository
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_core.services.validation import validate_quantity
from shopcrm_core.services.warehouse_service import WarehouseService
from sqlalchemy import select


@pytest_asyncio.fixture
async def product_with_stock(session) -> Product:
    """Товар с остатком 5."""
    p = Product(name="Stocked", price=10.00, unit="pc", stock=5)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
async def product_no_stock(session) -> Product:
    """Товар без остатка (stock=0)."""
    p = Product(name="Empty", price=10.00, unit="pc", stock=0)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


# ==================== ВИДИМОСТЬ (shop_repo) ====================

class TestVisibility:
    async def test_visible_when_stock_positive(self, session, product_with_stock):
        shop = ShopRepository(session)
        products = await shop.get_products_by_category(category_id=None)
        assert any(p.id == product_with_stock.id for p in products)

    async def test_hidden_when_stock_zero(self, session, product_no_stock):
        shop = ShopRepository(session)
        products = await shop.get_products_by_category(category_id=None)
        assert not any(p.id == product_no_stock.id for p in products)

    async def test_hidden_when_inactive(self, session, product_with_stock):
        product_with_stock.is_active = False
        await session.commit()
        shop = ShopRepository(session)
        products = await shop.get_products_by_category(category_id=None)
        assert not any(p.id == product_with_stock.id for p in products)


# ==================== ЛИМИТЫ КОРЗИНЫ (user_repo) ====================

class TestCartStockLimits:
    async def test_add_within_stock(self, session, user_a, product_with_stock):
        repo = UserRepository(session)
        user, error = await repo.add_to_cart(user_id=user_a.id, product_id=product_with_stock.id)
        assert error is None
        assert user is not None
        item = next(i for i in user.cart if i.product_id == product_with_stock.id)
        assert item.quantity == 1

    async def test_add_exceeds_stock(self, session, user_a, product_with_stock):
        """Товар с остатком 1: после добавления 1 шт. следующее — stock_limit."""
        product_with_stock.stock = 1
        await session.commit()
        repo = UserRepository(session)
        # Первое добавление — ок
        _, error1 = await repo.add_to_cart(user_id=user_a.id, product_id=product_with_stock.id)
        assert error1 is None
        # Второе — превышение
        _, error2 = await repo.add_to_cart(user_id=user_a.id, product_id=product_with_stock.id)
        assert error2 == "stock_limit"

    async def test_add_out_of_stock(self, session, user_a, product_no_stock):
        repo = UserRepository(session)
        _, error = await repo.add_to_cart(user_id=user_a.id, product_id=product_no_stock.id)
        assert error == "out_of_stock"

    async def test_increment_exceeds_stock(self, session, user_a, product_with_stock):
        """Увеличение количества в корзине не может превысить остаток."""
        product_with_stock.stock = 2
        await session.commit()
        repo = UserRepository(session)
        # Добавляем 1 шт.
        await repo.add_to_cart(user_id=user_a.id, product_id=product_with_stock.id)
        # Увеличиваем до 2 — ок
        _, error1 = await repo.update_cart_item(
            user_id=user_a.id, product_id=product_with_stock.id, change=1
        )
        assert error1 is None
        # Увеличиваем до 3 — превышение
        _, error2 = await repo.update_cart_item(
            user_id=user_a.id, product_id=product_with_stock.id, change=1
        )
        assert error2 == "stock_limit"

    async def test_decrement_always_allowed(self, session, user_a, product_with_stock):
        """Уменьшение количества всегда разрешено."""
        repo = UserRepository(session)
        await repo.add_to_cart(user_id=user_a.id, product_id=product_with_stock.id)
        _, error = await repo.update_cart_item(
            user_id=user_a.id, product_id=product_with_stock.id, change=-1
        )
        assert error is None


# ==================== СКЛАД (admin_repo + service) ====================

class TestWarehouse:
    async def test_add_stock(self, session, product_no_stock):
        service = WarehouseService(AdminRepository(session))
        product = await service.add_stock(product_no_stock.id, 10)
        assert product is not None
        assert product.stock == 10

    async def test_write_off_stock(self, session, product_with_stock):
        service = WarehouseService(AdminRepository(session))
        product = await service.write_off_stock(product_with_stock.id, 3)
        assert product is not None
        assert product.stock == 2

    async def test_write_off_floors_at_zero(self, session, product_with_stock):
        """Списание не может сделать остаток отрицательным."""
        service = WarehouseService(AdminRepository(session))
        product = await service.write_off_stock(product_with_stock.id, 100)
        assert product is not None
        assert product.stock == 0

    async def test_add_stock_not_found(self, session):
        service = WarehouseService(AdminRepository(session))
        product = await service.add_stock(99999, 5)
        assert product is None

    async def test_write_off_not_found(self, session):
        service = WarehouseService(AdminRepository(session))
        product = await service.write_off_stock(99999, 5)
        assert product is None


# ==================== ЖУРНАЛ ДВИЖЕНИЙ (stock_movements) ====================

async def _get_movements(session, product_id: int | None = None) -> list[StockMovement]:
    """Движения журнала (по товару или все), в порядке записи."""
    stmt = select(StockMovement).order_by(StockMovement.id)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


class TestStockMovements:
    async def test_add_stock_records_arrived(self, session, product_no_stock):
        service = WarehouseService(AdminRepository(session))
        await service.add_stock(product_no_stock.id, 10, admin_id=42)
        movements = await _get_movements(session, product_no_stock.id)
        assert len(movements) == 1
        m = movements[0]
        assert m.type == StockMovementType.ARRIVED.value
        assert m.quantity == 10
        assert m.stock_after == 10
        assert m.reserved_after == 0
        assert m.admin_id == 42
        assert m.order_id is None

    async def test_write_off_records_clamped_actual(self, session, product_with_stock):
        """stock=5, списание 100 → в журнале фактические 5, а не 100."""
        service = WarehouseService(AdminRepository(session))
        await service.write_off_stock(product_with_stock.id, 100, admin_id=42)
        movements = await _get_movements(session, product_with_stock.id)
        assert len(movements) == 1
        assert movements[0].type == StockMovementType.WRITTEN_OFF.value
        assert movements[0].quantity == 5
        assert movements[0].stock_after == 0
        assert movements[0].admin_id == 42

    async def test_write_off_empty_no_movement(self, session, product_no_stock):
        """Списание пустого товара (actual=0) не создаёт записи в журнале."""
        service = WarehouseService(AdminRepository(session))
        await service.write_off_stock(product_no_stock.id, 5)
        assert await _get_movements(session, product_no_stock.id) == []

    async def test_release_without_reservation_no_movement(self, session, product_with_stock):
        """Снятие брони без брони (actual=0) не создаёт записи в журнале."""
        service = WarehouseService(AdminRepository(session))
        await service.release_stock(product_with_stock.id, 3)
        assert await _get_movements(session, product_with_stock.id) == []

    async def test_reserve_release_confirm_record_order(self, session, user_a, product_with_stock):
        """Цикл брони по заказу: три движения со ссылкой на заказ."""
        order = Order(user_id=user_a.id, total_price=10.0)
        session.add(order)
        await session.commit()
        await session.refresh(order)

        service = WarehouseService(AdminRepository(session))
        await service.reserve_stock(product_with_stock.id, 2, order_id=order.id)
        await service.release_stock(product_with_stock.id, 2, order_id=order.id)
        await service.confirm_stock(product_with_stock.id, 2, order_id=order.id)

        movements = await _get_movements(session, product_with_stock.id)
        assert [m.type for m in movements] == [
            StockMovementType.RESERVED.value,
            StockMovementType.RELEASED.value,
            StockMovementType.SOLD.value,
        ]
        assert all(m.order_id == order.id for m in movements)
        assert all(m.admin_id is None for m in movements)
        # Снимки балансов после каждой операции
        assert movements[0].reserved_after == 2
        assert movements[1].reserved_after == 0
        assert movements[2].stock_after == 3
        assert movements[2].reserved_after == 0

    async def test_apply_order_stock_records_per_item(self, session, user_a, product_with_stock):
        """apply_order_stock создаёт по одному движению на позицию заказа."""
        p2 = Product(name="Second", price=5.00, unit="pc", stock=3)
        session.add(p2)
        await session.commit()
        await session.refresh(p2)

        order = Order(user_id=user_a.id, total_price=20.0)
        session.add(order)
        await session.commit()
        # Без refresh: он загрузил бы items пустым, и get_order_by_id
        # вернул бы тот же инстанс из identity map со stale-связью.
        session.add_all([
            OrderItem(order_id=order.id, product_id=product_with_stock.id,
                      quantity=2, price_at_purchase=10.0),
            OrderItem(order_id=order.id, product_id=p2.id,
                      quantity=1, price_at_purchase=5.0),
        ])
        await session.commit()

        service = WarehouseService(AdminRepository(session))
        # Перезагружаем заказ, чтобы items были загружены (selectin)
        order = await service.admin_repo.get_order_by_id(order.id)
        await service.apply_order_stock(order, "reserve")

        movements = await _get_movements(session)
        assert len(movements) == 2
        assert all(m.order_id == order.id for m in movements)
        by_product = {m.product_id: m for m in movements}
        assert by_product[product_with_stock.id].quantity == 2
        assert by_product[p2.id].quantity == 1

    async def test_reconciliation_invariant(self, session, user_a, product_no_stock):
        """Баланс восстанавливается из журнала: stock = Σarrived − Σwritten_off − Σsold."""
        order = Order(user_id=user_a.id, total_price=10.0)
        session.add(order)
        await session.commit()
        await session.refresh(order)

        service = WarehouseService(AdminRepository(session))
        await service.add_stock(product_no_stock.id, 10, admin_id=42)
        await service.write_off_stock(product_no_stock.id, 2, admin_id=42)
        await service.reserve_stock(product_no_stock.id, 3, order_id=order.id)
        await service.confirm_stock(product_no_stock.id, 3, order_id=order.id)

        product = await service.admin_repo.get_product_by_id(product_no_stock.id)
        movements = await _get_movements(session, product_no_stock.id)

        arrived = sum(m.quantity for m in movements if m.type == StockMovementType.ARRIVED.value)
        written_off = sum(m.quantity for m in movements if m.type == StockMovementType.WRITTEN_OFF.value)
        sold = sum(m.quantity for m in movements if m.type == StockMovementType.SOLD.value)
        assert product.stock == 10 - 2 - 3
        assert product.stock == arrived - written_off - sold
        assert product.total_arrived == arrived
        assert product.total_written_off == written_off
        assert product.total_sold == sold
        # Финальный снимок совпадает с текущим балансом
        assert movements[-1].stock_after == product.stock


# ==================== АРХИВАЦИЯ И ПОЛНОЕ УДАЛЕНИЕ ====================

class TestArchiveAndDelete:
    async def test_commit_changes_archives_removed_product(self, session, user_a, product_with_stock):
        """Товар, отсутствующий в черновике каталога, архивируется, а не удаляется."""
        # Черновик каталога: другой товар (original_id=999), product_with_stock не в списке
        tp = TempProduct(
            original_id=999, name="Other", description="", price=1.0,
            unit="pc", admin_id=user_a.id,
        )
        session.add(tp)
        await session.commit()

        # Движение по product_with_stock (проверим сохранение журнала)
        service = WarehouseService(AdminRepository(session))
        await service.add_stock(product_with_stock.id, 1, admin_id=user_a.id)
        movements_before = await _get_movements(session, product_with_stock.id)
        assert len(movements_before) == 1

        repo = AdminRepository(session)
        await repo.commit_changes(admin_id=user_a.id)

        # Товар архивирован, а не удалён
        archived = await repo.get_product_by_id(product_with_stock.id)
        assert archived is not None
        assert archived.is_active is False
        assert archived.stock == 6  # остаток сохранён (5 + 1)
        # Журнал сохранён
        movements_after = await _get_movements(session, product_with_stock.id)
        assert len(movements_after) == 1

    async def test_commit_changes_reactivates_alive_product(self, session, user_a, product_with_stock):
        """Товар, присутствующий в черновике, реактивируется (is_active=True)."""
        product_with_stock.is_active = False
        await session.commit()

        tp = TempProduct(
            original_id=product_with_stock.id, name="Stocked", description="",
            price=10.0, unit="pc", admin_id=user_a.id,
        )
        session.add(tp)
        await session.commit()

        repo = AdminRepository(session)
        await repo.commit_changes(admin_id=user_a.id)

        reactivated = await repo.get_product_by_id(product_with_stock.id)
        assert reactivated is not None
        assert reactivated.is_active is True

    async def test_sync_to_temp_skips_archived(self, session, user_a, product_with_stock):
        """Архивные товары не копируются в черновик каталога."""
        product_with_stock.is_active = False
        await session.commit()

        repo = AdminRepository(session)
        await repo.sync_to_temp(admin_id=user_a.id)

        result = await session.execute(
            select(TempProduct).where(TempProduct.admin_id == user_a.id)
        )
        temp_prods = list(result.scalars().all())
        assert all(tp.original_id != product_with_stock.id for tp in temp_prods)

    async def test_delete_product_blocks_on_stock(self, session, product_with_stock):
        """Удаление блокируется, если есть остаток (stock > 0)."""
        service = WarehouseService(AdminRepository(session))
        product, error = await service.delete_product(product_with_stock.id, admin_id=42)
        assert error == "has_stock"
        assert product is not None
        # Товар не удалён
        assert await AdminRepository(session).get_product_by_id(product_with_stock.id) is not None

    async def test_delete_product_blocks_on_reserved(self, session, product_with_stock):
        """Удаление блокируется, если есть активные заказы (reserved > 0)."""
        product_with_stock.stock = 0
        product_with_stock.reserved = 2
        await session.commit()
        service = WarehouseService(AdminRepository(session))
        product, error = await service.delete_product(product_with_stock.id, admin_id=42)
        assert error == "has_orders"
        assert await AdminRepository(session).get_product_by_id(product_with_stock.id) is not None

    async def test_delete_product_not_found(self, session):
        """Удаление несуществующего товара → not_found."""
        service = WarehouseService(AdminRepository(session))
        product, error = await service.delete_product(99999, admin_id=42)
        assert error == "not_found"
        assert product is None

    async def test_delete_product_success(self, session, product_with_stock):
        """Удаление при нулевых балансах: товар и журнал удаляются."""
        service = WarehouseService(AdminRepository(session))
        # Списать остаток до 0
        await service.write_off_stock(product_with_stock.id, 5, admin_id=42)
        movements_before = await _get_movements(session, product_with_stock.id)
        assert len(movements_before) == 1

        product, error = await service.delete_product(product_with_stock.id, admin_id=42)
        assert error is None
        # Товар удалён
        assert await AdminRepository(session).get_product_by_id(product_with_stock.id) is None
        # Журнал удалён (CASCADE)
        assert await _get_movements(session, product_with_stock.id) == []

    # --- Возврат из архива в каталог ---

    async def test_restore_product_success(self, session, product_with_stock):
        """Архивный товар возвращается в каталог (is_active=True)."""
        product_with_stock.is_active = False
        await session.commit()

        service = WarehouseService(AdminRepository(session))
        product, error = await service.restore_product(product_with_stock.id, admin_id=42)
        assert error is None
        assert product is not None
        assert product.is_active is True
        # Остаток не затронут
        assert product.stock == 5

    async def test_restore_product_not_found(self, session):
        """Восстановление несуществующего товара → not_found."""
        service = WarehouseService(AdminRepository(session))
        product, error = await service.restore_product(99999, admin_id=42)
        assert error == "not_found"
        assert product is None

    async def test_restore_product_already_active(self, session, product_with_stock):
        """Активный товар → already_active (без изменений)."""
        service = WarehouseService(AdminRepository(session))
        product, error = await service.restore_product(product_with_stock.id, admin_id=42)
        assert error == "already_active"
        assert product is not None
        assert product.is_active is True


# ==================== ВАЛИДАЦИЯ ====================

class TestValidateQuantity:
    def test_valid(self):
        qty, error = validate_quantity("5", "ru")
        assert qty == 5
        assert error is None

    def test_zero_invalid(self):
        qty, error = validate_quantity("0", "ru")
        assert qty is None
        assert error is not None

    def test_negative_invalid(self):
        qty, error = validate_quantity("-3", "ru")
        assert qty is None
        assert error is not None

    def test_non_numeric_invalid(self):
        qty, error = validate_quantity("abc", "ru")
        assert qty is None
        assert error is not None

    def test_float_invalid(self):
        qty, error = validate_quantity("2.5", "ru")
        assert qty is None
        assert error is not None

