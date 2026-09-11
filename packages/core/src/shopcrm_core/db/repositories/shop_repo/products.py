from sqlalchemy import select
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class ShopProductsMixin:

    @property
    def _product_repo(self) -> BaseRepository[Product]:
        return BaseRepository(Product, self.session)

    def _get_category_condition(self, category_id: int | None):
        """Формирует корректное SQL-условие для фильтрации по category_id."""
        if category_id is None:
            return Product.category_id.is_(None)
        return Product.category_id == category_id

    async def get_products_by_category(self, category_id: int | None) -> list[Product]:
        """Получить активные товары в категории."""
        logger.info(f"Fetching shop products by category_id={category_id}")
        return await self._product_repo.get_all(
            self._get_category_condition(category_id),
            Product.is_active.is_not(False)
        )

    async def get_product_by_id(self, product_id: int) -> Product | None:
        """Получить товар по ID."""
        logger.info(f"Fetching shop product id={product_id}")
        return await self._product_repo.get_by_id(product_id)

    async def get_next_product(self, category_id: int | None, current_product_id: int) -> Product | None:
        """Получить следующий активный товар (с закольцовыванием)."""
        logger.info(f"Fetching next product for category_id={category_id}, current_product_id={current_product_id}")

        category_cond = self._get_category_condition(category_id)

        # 1. Ищем следующий активный товар по возрастанию ID
        products = await self._product_repo.get_all(
            category_cond,
            Product.is_active.is_not(False),
            Product.id > current_product_id,
            order_by=Product.id.asc(),
            limit=1
        )
        if products:
            return products[0]

        # 2. Если дальше ничего нет — закольцовываемся на самый первый активный
        first_products = await self._product_repo.get_all(
            category_cond,
            Product.is_active.is_not(False),
            order_by=Product.id.asc(),
            limit=1
        )
        return first_products[0] if first_products else None

    async def get_prev_product(self, category_id: int | None, current_product_id: int) -> Product | None:
        """Получить предыдущий активный товар (с закольцовыванием)."""
        logger.info(f"Fetching previous product for category_id={category_id}, current_product_id={current_product_id}")

        category_cond = self._get_category_condition(category_id)

        # 1. Ищем предыдущий активный товар по убыванию ID
        products = await self._product_repo.get_all(
            category_cond,
            Product.is_active.is_not(False),
            Product.id < current_product_id,
            order_by=Product.id.desc(),
            limit=1
        )
        if products:
            return products[0]

        # 2. Если назад ничего нет — закольцовываемся на самый последний активный
        last_products = await self._product_repo.get_all(
            category_cond,
            Product.is_active.is_not(False),
            order_by=Product.id.desc(),
            limit=1
        )
        return last_products[0] if last_products else None