# keyboards/base.py
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


class BaseKeyboardFactory:
    """
    Базовый класс для всех фабрик inline-клавиатур.
    Обеспечивает кэширование шаблонов, локализацию и вспомогательные методы сборки.
    """
    # Кэш загруженных JSON шаблонов на уровне класса: {file_path: dict_data}
    _templates_cache: Dict[Path, Dict[str, Any]] = {}

    def __init__(self, json_path: Path, lang: str = "ru", default_lang: str = "en"):
        self.json_path = json_path
        self.lang = lang
        self.default_lang = default_lang
        self.template = self._get_or_load_template(json_path)

    @classmethod
    def _get_or_load_template(cls, path: Path) -> Dict[str, Any]:
        """Загружает JSON шаблон в память один раз (Singleton Pattern для дискового I/O)"""
        if path not in cls._templates_cache:
            try:
                with open(path, "r", encoding="utf-8") as file:
                    cls._templates_cache[path] = json.load(file)
                    logger.info(f"[KB FACTORY] Loaded keyboard template cache for: {path.name}")
            except Exception as e:
                logger.critical(f"[KB FACTORY] Failed to load keyboard json at {path}: {e}", exc_info=True)
                cls._templates_cache[path] = {}
        return cls._templates_cache[path]

    @classmethod
    def clear_cache(cls):
        """Очистка кэша на случай горячей перезагрузки конфигураций в рантайме"""
        cls._templates_cache.clear()

    def get_i18n_text(self, translations: Dict[str, str], default_text: str = "❌") -> str:
        """Безопасное извлечение перевода из словаря с цепочкой фолбэков"""
        if not isinstance(translations, dict):
            return default_text
        return (
                translations.get(self.lang)
                or translations.get(self.default_lang)
                or translations.get("ru")
                or next(iter(translations.values()), default_text)
        )

    def get_text_by_path(self, path: str, default: str = "") -> str:
        """Получение локализованного текста по вложенному dot-пути (e.g. 'admin_messages.errors.not_found')"""
        keys = path.split(".")
        current = self.template

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default

        if isinstance(current, dict):
            return self.get_i18n_text(current, default)
        return str(current) if current is not None else default

    def build_from_config(
            self,
            config_key: str,
            format_kwargs: Optional[Dict[str, Dict[str, Any]]] = None,
            callback_override: Optional[Dict[str, str]] = None
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Универсальный метод сборки клавиатуры прямо из JSON-конфигурации.

        :param config_key: Ключ раздела в JSON.
        :param format_kwargs: Словарь аргументов форматирования текста для конкретных кнопок.
                              Пример: {"btn_cart": {"cart": 5}}
        :param callback_override: Подмена callback_data. Пример: {"back": "admin_mainmenu"}
        """
        data = self.template.get(config_key)
        if not data:
            logger.critical(f"[KB FACTORY] Config key '{config_key}' not found!")
            return None

        buttons = data.get("buttons", {})
        sizes = data.get("sizes", [1])

        builder = InlineKeyboardBuilder()

        for original_callback, translations in buttons.items():
            btn_text = self.get_i18n_text(translations, default_text=original_callback)

            # Форматирование текста кнопки (если переданы переменные подстановки)
            if format_kwargs and original_callback in format_kwargs:
                try:
                    btn_text = btn_text.format(**format_kwargs[original_callback])
                except Exception as e:
                    logger.error(f"[KB FACTORY] Formatting error for button '{original_callback}': {e}")

            # Подмена callback_data
            actual_callback = (
                callback_override.get(original_callback, original_callback)
                if callback_override else original_callback
            )

            builder.button(text=btn_text, callback_data=actual_callback)

        builder.adjust(*sizes)
        return builder.as_markup()

    @staticmethod
    def create_pagination_row(
            current_page: int,
            total_pages: int,
            callback_prefix: str,
            extra_param: str = ""
    ) -> List[InlineKeyboardButton]:
        """Стандартный генератор ряда кнопки круговой пагинации"""
        if total_pages <= 0:
            return []

        prev_page = total_pages if current_page == 1 else current_page - 1
        next_page = 1 if current_page == total_pages else current_page + 1

        param_str = f":{extra_param}" if extra_param else ""

        return [
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{callback_prefix}{param_str}:{prev_page}"
            ),
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}",
                callback_data="noop"
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{callback_prefix}{param_str}:{next_page}"
            )
        ]