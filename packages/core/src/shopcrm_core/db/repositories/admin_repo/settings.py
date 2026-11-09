# database/repositories/admin_repo/settings.py
"""Репозиторий настроек магазина (таблица ``settings``, ключ-значение)."""
from shopcrm_core.db.models.setting import Setting
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class AdminSettingsMixin:

    @property
    def _setting_repo(self) -> BaseRepository[Setting]:
        return BaseRepository(Setting, self.session)

    async def get_setting(self, key: str) -> str | None:
        """Возвращает значение настройки по ключу (или None, если не задана)."""
        setting = await self._setting_repo.get_one(Setting.key == key)
        return setting.value if setting else None

    async def set_setting(self, key: str, value: str | None, updated_by: int | None = None) -> Setting:
        """Создаёт или обновляет настройку (upsert по ключу)."""
        logger.info(f"Setting '{key}' updated (by {updated_by})")
        setting = await self._setting_repo.get_one(Setting.key == key)
        if setting:
            setting.value = value
            setting.updated_by = updated_by
            await self.session.commit()
            await self.session.refresh(setting)
            return setting
        return await self._setting_repo.create(key=key, value=value, updated_by=updated_by)
