"""Тесты управления остатками на складе и лимитов корзины.

Проверяют:
  - видимость товара для клиента (is_active AND stock > 0)
  - лимиты корзины (нельзя заказать больше остатка)
  - пополнение/списание остатка (floor 0)
  - валидацию количества
"""
import pytest_asyncio
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.db.repositories.shop_repo import ShopRepository
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_core.services.validation import validate_quantity
from shopcrm_core.services.warehouse_service import WarehouseService


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

