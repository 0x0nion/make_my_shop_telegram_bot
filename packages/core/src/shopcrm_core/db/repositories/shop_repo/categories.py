from shopcrm_core.db.models.category import Category
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class ShopCategoriesMixin:

    @property
    def _category_repo(self) -> BaseRepository[Category]:
        return BaseRepository(Category, self.session)

    async def get_category_by_id(self, category_id: int) -> Category | None:
        """Получить категорию по ID."""
        logger.info(f"Fetching shop category id={category_id}")
        return await self._category_repo.get_by_id(category_id)

    async def get_categories_by_parent(self, parent_id: int | None = None) -> list[Category]:
        """Получить только активные подкатегории для указанного parent_id."""
        logger.info(f"Fetching shop categories by parent_id={parent_id}")

        # Корректное сравнение с NULL в SQL при parent_id=None
        parent_condition = (
            Category.parent_id.is_(None)
            if parent_id is None
            else Category.parent_id == parent_id
        )

        return await self._category_repo.get_all(
            parent_condition,
            Category.is_active.is_not(False),  # Учитывает True и старые записи (NULL)
            order_by=Category.id.asc()
        )