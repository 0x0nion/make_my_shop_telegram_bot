"""Локализация для Telegram-бота: ядро (shopcrm_core) + фабрика клавиатур aiogram."""
from shopcrm_core.locales.locale import Locale as _CoreLocale


class BotLocale(_CoreLocale):
    """Ядровой Locale с доступом к фабрике клавиатур бота."""

    @property
    def keyboards(self):
        from shopcrm_bot.keyboards.keyboard import KeyboardFactory

        return KeyboardFactory(locale=self)


# Алиас: код бота продолжает использовать привычное имя Locale
Locale = BotLocale

__all__ = ["Locale", "BotLocale"]
