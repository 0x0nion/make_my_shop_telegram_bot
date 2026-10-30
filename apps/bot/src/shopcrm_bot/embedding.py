"""API встраивания админ-секции во внешние приложения.

Для приложений, которые переиспользуют редактор магазина
(каталог/товары/приветствие/заказы) без запуска полноценного core-бота.

Пример (внешний dispatcher):

    from shopcrm_bot.embedding import (
        extract_admin_group_router,
        is_admin_shop_callback,
    )

    dp.include_router(extract_admin_group_router())

Хэндлеры ожидают в workflow data (DI-контракт):

    admin_repo: AdminRepository
    admin_service: AdminShopService
    user: User
    locale: Locale
    admin_ids: list[int]
"""
from aiogram import Router

from shopcrm_bot.handlers.admin import admin_group_router

# Callback-префиксы редактора магазина (единый источник истины).
# Внешние middleware используют их для гейтинга: только на эти callback'ы
# нужно создавать сессию схемы и DI-объекты.
ADMIN_SHOP_CALLBACK_PREFIXES: tuple[str, ...] = (
    "admin_catalog_",  # навигация каталога (admin_catalog_start, ...)
    "admin_edit_cat:",  # категории/товары + admin_edit_cat:save_shop
    "admin_item_",  # редактор товара
    "admin_edit_p_",  # редактирование товара
    "admin_del_photo_",  # удаление фото товара
    "admin_set_unit_",  # единица товара
    "admin_greeting",  # вход в редактор приветствия
    "admin_edit_wel_",  # приветствие: текст/фото
    "admin_shop_settings",  # настройки магазина
    "admin_payment_details",  # реквизиты оплаты
    "admin_edit_payment_text",  # текст реквизитов
)


def is_admin_shop_callback(data: str | None) -> bool:
    """Принадлежит ли callback-данные редактору магазина.

    Используется внешними middleware для решения, нужно ли создавать
    сессию схемы и DI-объекты для этого callback'а.
    """
    if not data:
        return False
    return any(data == p or data.startswith(p) for p in ADMIN_SHOP_CALLBACK_PREFIXES)


def extract_admin_group_router() -> Router:
    """Открепляет ``admin_group_router`` от дерева core-бота и возвращает его.

    Для переиспользования админ-секции (редактор магазина, заказы) во
    внешних приложениях. После вызова core-бот в том
    же процессе админ-секцию не получит — функция предназначена для
    процессов, которые НЕ запускают core-бота.

    Идемпотентна: повторный вызов возвращает тот же роутер.
    """
    parent = admin_group_router._parent_router
    if parent is not None:
        admin_group_router._parent_router = None
        if admin_group_router in parent.sub_routers:
            parent.sub_routers.remove(admin_group_router)
    return admin_group_router


__all__ = [
    "ADMIN_SHOP_CALLBACK_PREFIXES",
    "extract_admin_group_router",
    "is_admin_shop_callback",
]
