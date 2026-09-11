from shopcrm_core.db.models import LocaleText
from shopcrm_core.db.models.temp_models import TempLocaleText
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class AdminLocalesMixin:

    async def get_locale_text(
            self,
            entity_id: int,
            entity_type: str,
            language_code: str,
            use_temp: bool = False,
            admin_id: int = None
    ) -> str | None:
        if use_temp:
            repo = BaseRepository(TempLocaleText, self.session)
            item = await repo.get_one(
                TempLocaleText.entity_id == entity_id,
                TempLocaleText.entity_type == entity_type,
                TempLocaleText.language_code == language_code,
                TempLocaleText.admin_id == admin_id
            )
        else:
            repo = BaseRepository(LocaleText, self.session)
            item = await repo.get_one(
                LocaleText.entity_id == entity_id,
                LocaleText.entity_type == entity_type,
                LocaleText.language_code == language_code
            )
        return item.text if item else None

    async def get_temp_locales(self, entity_id: int, entity_type: str, admin_id: int):
        repo = BaseRepository(TempLocaleText, self.session)
        return await repo.get_all(
            TempLocaleText.entity_id == entity_id,
            TempLocaleText.entity_type == entity_type,
            TempLocaleText.admin_id == admin_id
        )

    async def update_temp_locale(
            self,
            entity_id: int,
            entity_type: str,
            language_code: str,
            text: str,
            admin_id: int
    ):
        logger.debug(f"Updating temp locale for entity_id={entity_id}, type='{entity_type}', lang='{language_code}', admin_id={admin_id}")
        repo = BaseRepository(TempLocaleText, self.session)
        locale = await repo.get_one(
            TempLocaleText.entity_id == entity_id,
            TempLocaleText.entity_type == entity_type,
            TempLocaleText.language_code == language_code,
            TempLocaleText.admin_id == admin_id
        )

        if locale:
            await repo.update(locale.id, text=text)
        else:
            await repo.create(
                entity_id=entity_id,
                entity_type=entity_type,
                language_code=language_code,
                text=text,
                admin_id=admin_id
            )

    async def update_temp_locale_for_all_languages(
            self,
            entity_id: int,
            entity_type: str,
            text: str,
            admin_id: int
    ):
        for lang_code in self.SUPPORTED_LANGUAGES:
            await self.update_temp_locale(
                entity_id=entity_id,
                entity_type=entity_type,
                language_code=lang_code,
                text=text,
                admin_id=admin_id
            )

    async def delete_temp_locale_for_all_languages(
            self,
            entity_id: int,
            entity_type: str,
            admin_id: int
    ):
        logger.info(f"Deleting temp locales for entity_id={entity_id}, type='{entity_type}', admin_id={admin_id}")
        repo = BaseRepository(TempLocaleText, self.session)
        await repo.delete_where(
            TempLocaleText.entity_id == entity_id,
            TempLocaleText.entity_type == entity_type,
            TempLocaleText.admin_id == admin_id
        )