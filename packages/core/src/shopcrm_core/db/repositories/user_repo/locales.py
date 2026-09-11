from typing import Optional, Sequence
from sqlalchemy import or_
from shopcrm_core.db.models.locales import LocaleText
from shopcrm_core.db.repositories.base_repo import BaseRepository


class UserLocaleMixin:
    """Миксин для работы с локалями и динамическими текстами/медиа на стороне пользователя."""

    @property
    def _locale_repo(self) -> BaseRepository[LocaleText]:
        return BaseRepository(LocaleText, self.session)

    async def get_locale_text(
            self,
            entity_type: str,
            entity_id: int = 0,
            lang_code: str = "ru",
            default_lang: str = "ru"
    ) -> Optional[str]:
        """Получение одного текста с автоматическим фолбэком на язык по умолчанию."""
        # Запрашиваем сразу и целевой, и дефолтный язык за 1 запрос
        stmt_conditions = [
            LocaleText.entity_type == entity_type,
            LocaleText.entity_id == entity_id,
            LocaleText.language_code.in_([lang_code, default_lang])
        ]

        locales = await self._locale_repo.get_all(*stmt_conditions)
        if not locales:
            return None

        # Ищем совпадение по целевому языку
        target_locale = next((loc for loc in locales if loc.language_code == lang_code), None)
        if target_locale and target_locale.text:
            return target_locale.text

        # Фолбэк на дефолтный язык
        fallback_locale = next((loc for loc in locales if loc.language_code == default_lang), None)
        return fallback_locale.text if fallback_locale else None

    async def get_welcome_card(self, lang_code: str = "ru") -> tuple[str, Optional[str]]:
        """
        Загружает приветственный текст и фото за 1 эффективный запрос к БД.
        """
        # Запрашиваем сразу welcome_message и welcome_photo для обоих языков
        locales = await self._locale_repo.get_all(
            LocaleText.entity_type.in_(["welcome_message", "welcome_photo"]),
            LocaleText.entity_id == 0,
            LocaleText.language_code.in_([lang_code, "ru"])
        )

        # Функция-помощник для извлечения значения из полученного списка
        def extract_text(entity_type: str) -> Optional[str]:
            # Пробуем найти целевой язык
            match = next((l for l in locales if l.entity_type == entity_type and l.language_code == lang_code), None)
            if match and match.text:
                return match.text
            # Пробуем найти дефолтный язык (ru)
            match_fallback = next((l for l in locales if l.entity_type == entity_type and l.language_code == "ru"),
                                  None)
            return match_fallback.text if match_fallback else None

        text = extract_text("welcome_message") or "👋 Добро пожаловать в наш магазин!"
        photo_id = extract_text("welcome_photo")

        # Простая проверка: очищаем только пустые строки или явные пробелы
        if photo_id:
            photo_id = photo_id.strip()
            if not photo_id:
                photo_id = None

        return text, photo_id