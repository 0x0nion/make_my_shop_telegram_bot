# database/repositories/admin_repo/products.py`

from shopcrm_core.constants import StockMovementType
from shopcrm_core.db.models import LocaleText
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.models.stock_movement import StockMovement
from shopcrm_core.db.models.temp_models import TempLocaleText, TempProduct
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.locales.units import DEFAULT_UNIT
from shopcrm_core.logging import logger


class AdminProductsMixin:

    def _get_product_repo(self, use_temp: bool = False) -> BaseRepository:
        model = TempProduct if use_temp else Product
        return BaseRepository(model, self.session)

    def _record_stock_movement(
            self,
            product: Product,
            movement_type: str,
            quantity: int,
            stock_after: int,
            reserved_after: int,
            order_id: int | None = None,
            admin_id: int | None = None,
            comment: str | None = None,
    ) -> None:
        """Добавить движение в сессию (без отдельного commit).

        Запись попадает в БД тем же коммитом, что и обновление балансов
        товара (commit внутри ``update``) — журнал и балансы
        обновляются атомарно.
        """
        self.session.add(StockMovement(
            product_id=product.id,
            type=movement_type,
            quantity=quantity,
            stock_after=stock_after,
            reserved_after=reserved_after,
            order_id=order_id,
            admin_id=admin_id,
            comment=comment,
        ))

    async def get_product_by_id(
            self,
            product_id: int,
            use_temp: bool = False,
            admin_id: int | None = None
    ) -> Product | TempProduct | None:
        repo = self._get_product_repo(use_temp)
        if use_temp:
            return await repo.get_one(TempProduct.id == product_id, TempProduct.admin_id == admin_id)
        return await repo.get_by_id(product_id)

    async def get_products_by_category(
            self,
            category_id: int | None,
            use_temp: bool = False,
            admin_id: int | None = None
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
            admin_id: int | None = None
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
        else:
            # Аудит: кто создал товар (для реальных товаров; у черновиков такого поля нет)
            data["updated_by"] = admin_id

        new_product = await repo.create_without_commit(**data)

        # Сохраняем название в локальное хранилище для всех языков
        # (единое значение по умолчанию, переводы по языкам — позже),
        # аналогично паттерну категорий
        locale_repo = BaseRepository(TempLocaleText if use_temp else LocaleText, self.session)
        for lang_code in self.SUPPORTED_LANGUAGES:
            loc_data = {
                "entity_id": new_product.id,
                "entity_type": "product_name",
                "language_code": lang_code,
                "text": name
            }
            if use_temp:
                loc_data["admin_id"] = admin_id
            await locale_repo.create_without_commit(**loc_data)

        await self.session.commit()
        return new_product

    async def delete_product(self, product_id: int, use_temp: bool = False, admin_id: int | None = None):
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
            # Явно удаляем журнал движений: в продакшене это также делает
            # CASCADE, но явное удаление надёжнее и работает в SQLite-тестах.
            await BaseRepository(StockMovement, self.session).delete_where(
                StockMovement.product_id == product_id
            )
            await BaseRepository(Product, self.session).delete_by_id(product_id)
            await BaseRepository(LocaleText, self.session).delete_where(
                LocaleText.entity_id == product_id,
                LocaleText.entity_type.like('%product%')
            )

    async def get_all_products(self) -> list[Product]:
        """Все реальные товары (для склада) с остатком."""
        return await self._get_product_repo(use_temp=False).get_all(
            order_by=Product.name
        )

    async def add_stock(
            self, product_id: int, qty: int, admin_id: int | None = None, comment: str | None = None
    ) -> Product | None:
        """Пополнить остаток товара на складе (только реальные товары).

        Увеличивает ``stock`` и накопительную метрику ``total_arrived``.
        Движение фиксируется в журнале ``stock_movements`` той же
        транзакцией, что и обновление балансов.
        """
        logger.info(f"Adding stock: product_id={product_id}, qty={qty}")
        product = await self.get_product_by_id(product_id)
        if not product:
            return None
        new_stock = (product.stock or 0) + qty
        new_total_arrived = (product.total_arrived or 0) + qty
        self._record_stock_movement(
            product,
            StockMovementType.ARRIVED.value,
            qty,
            stock_after=new_stock,
            reserved_after=product.reserved or 0,
            admin_id=admin_id,
            comment=comment,
        )
        update_kwargs = {"stock": new_stock, "total_arrived": new_total_arrived}
        if admin_id is not None:
            update_kwargs["updated_by"] = admin_id
        await self._get_product_repo(use_temp=False).update(product.id, **update_kwargs)
        return await self.get_product_by_id(product_id)

    async def write_off_stock(
            self, product_id: int, qty: int, admin_id: int | None = None, comment: str | None = None
    ) -> Product | None:
        """Списать остаток товара (не ниже 0). Только реальные товары.

        Списывает ``min(qty, stock)`` и увеличивает ``total_written_off``
        на фактическое списание (чтобы не уйти в минус). В журнал
        попадает фактическое (за кламп) количество.
        """
        logger.info(f"Writing off stock: product_id={product_id}, qty={qty}")
        product = await self.get_product_by_id(product_id)
        if not product:
            return None
        current_stock = product.stock or 0
        actual = min(qty, current_stock)
        new_stock = current_stock - actual
        new_total_written_off = (product.total_written_off or 0) + actual
        if actual > 0:
            self._record_stock_movement(
                product,
                StockMovementType.WRITTEN_OFF.value,
                actual,
                stock_after=new_stock,
                reserved_after=product.reserved or 0,
                admin_id=admin_id,
                comment=comment,
            )
        update_kwargs = {"stock": new_stock, "total_written_off": new_total_written_off}
        if admin_id is not None:
            update_kwargs["updated_by"] = admin_id
        await self._get_product_repo(use_temp=False).update(product.id, **update_kwargs)
        return await self.get_product_by_id(product_id)

    async def reserve_stock(
            self, product_id: int, qty: int, order_id: int | None = None
    ) -> Product | None:
        """Заморозить часть остатка под заказ (бронирование).

        Увеличивает ``reserved``. Физический ``stock`` не меняется —
        товар остаётся на складе, но становится недоступен для новых заказов.
        """
        logger.info(f"Reserving stock: product_id={product_id}, qty={qty}")
        product = await self.get_product_by_id(product_id)
        if not product:
            return None
        new_reserved = (product.reserved or 0) + qty
        self._record_stock_movement(
            product,
            StockMovementType.RESERVED.value,
            qty,
            stock_after=product.stock or 0,
            reserved_after=new_reserved,
            order_id=order_id,
        )
        await self._get_product_repo(use_temp=False).update(product.id, reserved=new_reserved)
        return await self.get_product_by_id(product_id)

    async def release_stock(
            self, product_id: int, qty: int, order_id: int | None = None
    ) -> Product | None:
        """Разморозить часть остатка (отмена заказа).

        Уменьшает ``reserved`` (не ниже 0). Физический ``stock`` не меняется —
        товар возвращается в доступный остаток. В журнал попадает
        фактическое (за кламп) количество.
        """
        logger.info(f"Releasing stock: product_id={product_id}, qty={qty}")
        product = await self.get_product_by_id(product_id)
        if not product:
            return None
        current_reserved = product.reserved or 0
        actual = min(qty, current_reserved)
        new_reserved = current_reserved - actual
        if actual > 0:
            self._record_stock_movement(
                product,
                StockMovementType.RELEASED.value,
                actual,
                stock_after=product.stock or 0,
                reserved_after=new_reserved,
                order_id=order_id,
            )
        await self._get_product_repo(use_temp=False).update(product.id, reserved=new_reserved)
        return await self.get_product_by_id(product_id)

    async def confirm_stock(
            self, product_id: int, qty: int, order_id: int | None = None
    ) -> Product | None:
        """Списать товар со склада по завершённому заказу.

        Уменьшает ``stock`` и ``reserved``, увеличивает ``total_sold``.
        Товар физически покидает склад.
        """
        logger.info(f"Confirming stock: product_id={product_id}, qty={qty}")
        product = await self.get_product_by_id(product_id)
        if not product:
            return None
        new_stock = max((product.stock or 0) - qty, 0)
        new_reserved = max((product.reserved or 0) - qty, 0)
        new_total_sold = (product.total_sold or 0) + qty
        self._record_stock_movement(
            product,
            StockMovementType.SOLD.value,
            qty,
            stock_after=new_stock,
            reserved_after=new_reserved,
            order_id=order_id,
        )
        await self._get_product_repo(use_temp=False).update(
            product.id,
            stock=new_stock,
            reserved=new_reserved,
            total_sold=new_total_sold,
        )
        return await self.get_product_by_id(product_id)

    async def update_product_field(
            self,
            product_id: int,
            field: str,
            value: any,
            use_temp: bool = False,
            admin_id: int | None = None
    ):
        logger.debug(
            f"Updating product id={product_id} field '{field}' to '{value}' (use_temp={use_temp}, admin_id={admin_id})")
        repo = self._get_product_repo(use_temp)
        item = await self.get_product_by_id(product_id, use_temp=use_temp, admin_id=admin_id)
        if item:
            update_kwargs = {field: value}
            # Аудит: кто изменил товар (update() сам отфильтрует поле для черновиков)
            if admin_id is not None and field != "updated_by":
                update_kwargs["updated_by"] = admin_id
            await repo.update(item.id, **update_kwargs)
            # Держим локальное хранилище названия в актуальном состоянии
            # (единое значение для всех языков)
            if field == "name":
                await self.set_locale_text_for_all_languages(
                    entity_id=item.id,
                    entity_type="product_name",
                    text=value,
                    use_temp=use_temp,
                    admin_id=admin_id,
                )