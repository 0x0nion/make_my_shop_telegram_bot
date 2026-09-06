from shopcrm_core.db.models import LocaleText
from shopcrm_core.db.models.category import Category
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.models.temp_models import TempCategory, TempProduct, TempLocaleText
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class AdminCategoriesMixin:

    def _get_category_repo(self, use_temp: bool = False) -> BaseRepository:
        model = TempCategory if use_temp else Category
        return BaseRepository(model, self.session)

    async def get_category_by_id(
            self,
            category_id: int,
            use_temp: bool = False,
            admin_id: int = None
    ) -> Category | TempCategory | None:
        repo = self._get_category_repo(use_temp)
        if use_temp:
            return await repo.get_one(TempCategory.id == category_id, TempCategory.admin_id == admin_id)
        return await repo.get_by_id(category_id)

    async def get_categories_by_parent(
            self,
            parent_id: int | None = None,
            use_temp: bool = False,
            admin_id: int = None
    ) -> list:
        repo = self._get_category_repo(use_temp)
        if use_temp:
            return await repo.get_all(TempCategory.parent_id == parent_id, TempCategory.admin_id == admin_id)
        return await repo.get_all(Category.parent_id == parent_id)

    async def create_category(
            self,
            name: str,
            parent_id: int | None = None,
            use_temp: bool = False,
            admin_id: int = None
    ) -> Category | TempCategory:
        logger.info(f"Creating category '{name}' (parent_id={parent_id}, use_temp={use_temp}, admin_id={admin_id})")
        cat_repo = self._get_category_repo(use_temp)

        data = {"name": name, "parent_id": parent_id}
        if use_temp:
            data["admin_id"] = admin_id

        new_category = await cat_repo.create_without_commit(**data)

        locale_repo = BaseRepository(TempLocaleText if use_temp else LocaleText, self.session)
        for lang_code in self.SUPPORTED_LANGUAGES:
            loc_data = {
                "entity_id": new_category.id,
                "entity_type": "category_name",
                "language_code": lang_code,
                "text": name
            }
            if use_temp:
                loc_data["admin_id"] = admin_id
            await locale_repo.create_without_commit(**loc_data)

        await self.session.commit()
        return new_category

    async def _get_temp_subcategory_ids(self, parent_id: int, admin_id: int, accumulated: list):
        repo = BaseRepository(TempCategory, self.session)
        subs = await repo.get_all(TempCategory.parent_id == parent_id, TempCategory.admin_id == admin_id)
        for s in subs:
            accumulated.append(s.id)
            await self._get_temp_subcategory_ids(s.id, admin_id, accumulated)

    async def _get_real_subcategory_ids(self, parent_id: int, accumulated: list):
        repo = BaseRepository(Category, self.session)
        subs = await repo.get_all(Category.parent_id == parent_id)
        for s in subs:
            accumulated.append(s.id)
            await self._get_real_subcategory_ids(s.id, accumulated)

    async def delete_category(self, category_id: int, use_temp: bool = False, admin_id: int = None):
        logger.info(f"Deleting category id={category_id} (use_temp={use_temp}, admin_id={admin_id})")
        all_cat_ids = [category_id]

        if use_temp:
            await self._get_temp_subcategory_ids(category_id, admin_id, all_cat_ids)

            await BaseRepository(TempProduct, self.session).delete_where(
                TempProduct.category_id.in_(all_cat_ids),
                TempProduct.admin_id == admin_id
            )
            await BaseRepository(TempCategory, self.session).delete_where(
                TempCategory.id.in_(all_cat_ids),
                TempCategory.admin_id == admin_id
            )
            await BaseRepository(TempLocaleText, self.session).delete_where(
                TempLocaleText.entity_id.in_(all_cat_ids),
                TempLocaleText.entity_type.like('%category%'),
                TempLocaleText.admin_id == admin_id
            )
        else:
            await self._get_real_subcategory_ids(category_id, all_cat_ids)

            await BaseRepository(Product, self.session).delete_where(Product.category_id.in_(all_cat_ids))
            await BaseRepository(Category, self.session).delete_where(Category.id.in_(all_cat_ids))
            await BaseRepository(LocaleText, self.session).delete_where(
                LocaleText.entity_id.in_(all_cat_ids),
                LocaleText.entity_type.like('%category%')
            )


