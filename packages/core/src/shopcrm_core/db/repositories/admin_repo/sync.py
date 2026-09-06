from sqlalchemy import select, delete

from shopcrm_core.db.models import LocaleText
from shopcrm_core.db.models.category import Category
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.models.temp_models import TempCategory, TempProduct, TempLocaleText
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class AdminSyncMixin:

    async def sync_to_temp(self, admin_id: int):
        logger.info(f"Syncing real data to temp tables for admin_id={admin_id}")

        # 1. Очистка временных данных через BaseRepository
        await BaseRepository(TempCategory, self.session).delete_where(TempCategory.admin_id == admin_id)
        await BaseRepository(TempProduct, self.session).delete_where(TempProduct.admin_id == admin_id)
        await BaseRepository(TempLocaleText, self.session).delete_where(TempLocaleText.admin_id == admin_id)

        # 2. Синхронизация категорий
        cats = await BaseRepository(Category, self.session).get_all()

        real_to_temp_cat_id = {}
        temp_cats_pairs = []

        for cat in cats:
            tc = TempCategory(
                original_id=cat.id, name=cat.name, parent_id=None, admin_id=admin_id
            )
            self.session.add(tc)
            temp_cats_pairs.append((cat, tc))

        await self.session.flush()

        for cat, tc in temp_cats_pairs:
            real_to_temp_cat_id[cat.id] = tc.id

        for cat, tc in temp_cats_pairs:
            if cat.parent_id is not None:
                tc.parent_id = real_to_temp_cat_id.get(cat.parent_id)

        # 3. Синхронизация продуктов
        prods = await BaseRepository(Product, self.session).get_all()
        temp_prods_pairs = []
        for p in prods:
            tp = TempProduct(
                original_id=p.id, name=p.name, description=p.description,
                price=p.price, unit=p.unit, image_id=p.image_id,
                category_id=real_to_temp_cat_id.get(p.category_id), admin_id=admin_id
            )
            self.session.add(tp)
            temp_prods_pairs.append((p, tp))

        await self.session.flush()

        # 4. Синхронизация локалей
        locales = await BaseRepository(LocaleText, self.session).get_all()
        for loc in locales:
            target_id = None
            if loc.entity_id == 0:
                target_id = 0
            elif "category" in loc.entity_type:
                target_id = real_to_temp_cat_id.get(loc.entity_id)
            elif "product" in loc.entity_type:
                temp_p = next((tp for p, tp in temp_prods_pairs if p.id == loc.entity_id), None)
                if temp_p:
                    target_id = temp_p.id

            if target_id is not None:
                self.session.add(TempLocaleText(
                    entity_id=target_id,
                    entity_type=loc.entity_type,
                    language_code=loc.language_code,
                    text=loc.text,
                    admin_id=admin_id
                ))

        await self.session.commit()
        logger.info(
            f"Successfully synced data to temp for admin_id={admin_id} (Categories: {len(cats)}, Products: {len(temp_prods_pairs)})")

    async def commit_changes(self, admin_id: int):
        logger.info(f"Committing changes from temp tables to real database for admin_id={admin_id}")

        temp_cat_repo = BaseRepository(TempCategory, self.session)
        temp_prod_repo = BaseRepository(TempProduct, self.session)
        temp_locale_repo = BaseRepository(TempLocaleText, self.session)

        temp_cats = await temp_cat_repo.get_all(TempCategory.admin_id == admin_id)
        temp_prods = await temp_prod_repo.get_all(TempProduct.admin_id == admin_id)
        temp_locales = await temp_locale_repo.get_all(TempLocaleText.admin_id == admin_id)

        alive_cat_ids = [tc.original_id for tc in temp_cats if tc.original_id is not None]
        alive_prod_ids = [tp.original_id for tp in temp_prods if tp.original_id is not None]

        cat_repo = BaseRepository(Category, self.session)
        prod_repo = BaseRepository(Product, self.session)
        locale_repo = BaseRepository(LocaleText, self.session)

        # 1. Удаление старых данных
        if alive_prod_ids:
            await prod_repo.delete_where(~Product.id.in_(alive_prod_ids))
        else:
            await prod_repo.delete_where()

        if alive_cat_ids:
            await cat_repo.delete_where(~Category.id.in_(alive_cat_ids))
        else:
            await cat_repo.delete_where()

        # Удаляем локали несуществующих сущностей
        await locale_repo.delete_where(
            ~((LocaleText.entity_id.in_(alive_prod_ids) & LocaleText.entity_type.like('%product%')) |
              (LocaleText.entity_id.in_(alive_cat_ids) & LocaleText.entity_type.like('%category%')) |
              (LocaleText.entity_id == 0))
        )

        # 2. Обновление и создание категорий
        real_cats = await cat_repo.get_all(Category.id.in_(alive_cat_ids)) if alive_cat_ids else []
        real_cats_dict = {c.id: c for c in real_cats}

        temp_to_real_id = {}
        new_cats_pairs = []

        for tc in temp_cats:
            if tc.original_id is not None:
                temp_to_real_id[tc.id] = tc.original_id
                if real_cats_dict.get(tc.original_id):
                    real_cats_dict[tc.original_id].name = tc.name
            else:
                new_cat = Category(name=tc.name)
                self.session.add(new_cat)
                new_cats_pairs.append((tc, new_cat))

        await self.session.flush()
        for tc, new_cat in new_cats_pairs:
            temp_to_real_id[tc.id] = new_cat.id

        # 2.1 Обновление parent_id
        real_cats_all = await cat_repo.get_all()
        real_cats_all_dict = {c.id: c for c in real_cats_all}
        for tc in temp_cats:
            real_cat_id = temp_to_real_id.get(tc.id)
            if real_cat_id and real_cat_id in real_cats_all_dict:
                real_cats_all_dict[real_cat_id].parent_id = temp_to_real_id.get(tc.parent_id)

        # 3. Обновление продуктов
        real_prods = await prod_repo.get_all(Product.id.in_(alive_prod_ids)) if alive_prod_ids else []
        real_prods_dict = {p.id: p for p in real_prods}
        temp_to_real_prod_id = {}
        new_prods_pairs = []

        for tp in temp_prods:
            real_cat_id = temp_to_real_id.get(tp.category_id)
            if tp.original_id is not None:
                temp_to_real_prod_id[tp.id] = tp.original_id
                real_prod = real_prods_dict.get(tp.original_id)
                if real_prod:
                    real_prod.name, real_prod.description = tp.name, tp.description
                    real_prod.price, real_prod.unit = tp.price, tp.unit
                    real_prod.image_id, real_prod.category_id = tp.image_id, real_cat_id
            else:
                new_prod = Product(
                    name=tp.name, description=tp.description, price=tp.price,
                    unit=tp.unit, image_id=tp.image_id, category_id=real_cat_id
                )
                self.session.add(new_prod)
                new_prods_pairs.append((tp, new_prod))

        await self.session.flush()
        for tp, new_prod in new_prods_pairs:
            temp_to_real_prod_id[tp.id] = new_prod.id

        # 4. Финализация локалей (1 запрос вместо N)
        all_real_cat_ids = list(temp_to_real_id.values())
        all_real_prod_ids = list(temp_to_real_prod_id.values())

        existing_locales = await locale_repo.get_all(
            (LocaleText.entity_id == 0) |
            (LocaleText.entity_id.in_(all_real_cat_ids) & LocaleText.entity_type.like('%category%')) |
            (LocaleText.entity_id.in_(all_real_prod_ids) & LocaleText.entity_type.like('%product%'))
        )
        existing_locales_map = {
            (loc.entity_id, loc.entity_type, loc.language_code): loc
            for loc in existing_locales
        }

        active_locale_keys = set()

        for tl in temp_locales:
            if tl.entity_id == 0:
                real_id = 0
            elif "category" in tl.entity_type:
                real_id = temp_to_real_id.get(tl.entity_id)
            elif "product" in tl.entity_type:
                real_id = temp_to_real_prod_id.get(tl.entity_id)
            else:
                continue

            if real_id is not None:
                key = (real_id, tl.entity_type, tl.language_code)
                active_locale_keys.add(key)

                if key in existing_locales_map:
                    existing_locales_map[key].text = tl.text
                else:
                    self.session.add(LocaleText(
                        entity_id=real_id,
                        entity_type=tl.entity_type,
                        language_code=tl.language_code,
                        text=tl.text
                    ))

        for loc in existing_locales:
            if (loc.entity_id, loc.entity_type, loc.language_code) not in active_locale_keys:
                await self.session.delete(loc)

        # 5. Очистка временных
        await temp_cat_repo.delete_where(TempCategory.admin_id == admin_id)
        await temp_prod_repo.delete_where(TempProduct.admin_id == admin_id)
        await temp_locale_repo.delete_where(TempLocaleText.admin_id == admin_id)

        await self.session.commit()
        logger.info(f"Successfully committed changes for admin_id={admin_id}")