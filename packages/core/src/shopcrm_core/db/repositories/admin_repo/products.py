# database/repositories/admin_repo/products.py`

from shopcrm_core.db.models import LocaleText
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.models.temp_models import TempProduct, TempLocaleText
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.locales.units import DEFAULT_UNIT
from shopcrm_core.logging import logger


class AdminProductsMixin:

    def _get_product_repo(self, use_temp: bool = False) -> BaseRepository:
        model = TempProduct if use_temp else Product
        return BaseRepository(model, self.session)

    async def get_product_by_id(
            self,
            product_id: int,
            use_temp: bool = False,
            admin_id: int = None
    ) -> Product | TempProduct | None:
        repo = self._get_product_repo(use_temp)
        if use_temp:
            return await repo.get_one(TempProduct.id == product_id, TempProduct.admin_id == admin_id)
        return await repo.get_by_id(product_id)

    async def get_products_by_category(
            self,
            category_id: int | None,
            use_temp: bool = False,
            admin_id: int = None
    ) -> list:
        repo = self._get_product_repo(use_temp)
        if use_temp:
            return await repo.get_all(TempProduct.category_id == category_id, TempProduct.admin_id == admin_id)
        return await repo.get_all(Product.category_id == category_id)

    async def create_product(
            self,
            name: str,
            description: str,
            price: float,
            category_id: int | None,
            image_id: str | None = None,
            unit: str = DEFAULT_UNIT.value,
            use_temp: bool = False,
            admin_id: int = None
    ) -> Product | TempProduct:
        logger.info(f"Creating product '{name}' (category_id={category_id}, use_temp={use_temp}, admin_id={admin_id})")
        repo = self._get_product_repo(use_temp)
        data = {
            "name": name,
            "description": description,
            "price": price,
            "category_id": category_id,
            "image_id": image_id,
            "unit": unit
        }
        if use_temp:
            data["admin_id"] = admin_id

        return await repo.create(**data)

    async def delete_product(self, product_id: int, use_temp: bool = False, admin_id: int = None):
        logger.info(f"Deleting product id={product_id} (use_temp={use_temp}, admin_id={admin_id})")
        if use_temp:
            await BaseRepository(TempProduct, self.session).delete_where(
                TempProduct.id == product_id, TempProduct.admin_id == admin_id
            )
            await BaseRepository(TempLocaleText, self.session).delete_where(
                TempLocaleText.entity_id == product_id,
                TempLocaleText.entity_type.like('%product%'),
                TempLocaleText.admin_id == admin_id
            )
        else:
            await BaseRepository(Product, self.session).delete_by_id(product_id)
            await BaseRepository(LocaleText, self.session).delete_where(
                LocaleText.entity_id == product_id,
                LocaleText.entity_type.like('%product%')
            )

    async def update_product_field(
            self,
            product_id: int,
            field: str,
            value: any,
            use_temp: bool = False,
            admin_id: int = None
    ):
        logger.debug(
            f"Updating product id={product_id} field '{field}' to '{value}' (use_temp={use_temp}, admin_id={admin_id})")
        repo = self._get_product_repo(use_temp)
        item = await self.get_product_by_id(product_id, use_temp=use_temp, admin_id=admin_id)
        if item:
            await repo.update(item.id, **{field: value})