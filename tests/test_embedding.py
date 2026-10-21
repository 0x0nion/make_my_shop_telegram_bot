"""Тесты публичного API встраивания (``shopcrm_bot.embedding``).

Проверяют:
- ``extract_admin_group_router`` корректно открепляет роутер от дерева
  core-бота и идемпотентен;
- ``is_admin_shop_callback`` покрывает все callback'ы редактора магазина
  (контракт: переименование префикса в хэндлерах без обновления кортежа
  упадёт здесь) и отклоняет чужие callback'ы.
"""
import pytest
from aiogram import Router
from shopcrm_bot import embedding
from shopcrm_bot.handlers import routers as core_routers
from shopcrm_bot.handlers.admin import admin_group_router


@pytest.fixture(autouse=True)
def _restore_router():
    """``extract`` мутирует глобальный синглтон — после каждого теста
    возвращаем роутер в дерево core-бота, чтобы не влиять на другие тесты."""
    yield
    if admin_group_router._parent_router is None:
        core_routers.include_router(admin_group_router)


class TestExtractAdminGroupRouter:
    def test_returns_router(self):
        """Возвращает экземпляр Router."""
        router = embedding.extract_admin_group_router()
        assert isinstance(router, Router)

    def test_returns_admin_group_router(self):
        """Возвращает именно admin_group_router (синглтон)."""
        assert embedding.extract_admin_group_router() is admin_group_router

    def test_detaches_from_core_routers(self):
        """После extract роутер не в sub_routers у core-бота."""
        assert admin_group_router in core_routers.sub_routers
        embedding.extract_admin_group_router()
        assert admin_group_router not in core_routers.sub_routers

    def test_idempotent(self):
        """Повторный вызов возвращает тот же объект и не падает."""
        first = embedding.extract_admin_group_router()
        second = embedding.extract_admin_group_router()
        assert first is second

    def test_sub_routers_intact(self):
        """Под-роутеры (shop/orders/main) остаются на месте."""
        router = embedding.extract_admin_group_router()
        assert len(router.sub_routers) >= 3


class TestIsAdminShopCallback:
    @pytest.mark.parametrize(
        "data",
        [
            # каталог
            "admin_catalog_start",
            "admin_catalog_category:5",
            # категории/товары + сохранение
            "admin_edit_cat:save_shop",
            "admin_edit_cat:add_cat_1",
            "admin_edit_cat:del_item_3",
            # редактор товара
            "admin_item_7",
            "admin_edit_p_3",
            "admin_del_photo_2",
            "admin_set_unit_1",
            # приветствие
            "admin_greeting",
            "admin_edit_wel_text",
            "admin_edit_wel_photo",
            # настройки/оплата
            "admin_shop_settings",
            "admin_payment_details",
            "admin_edit_payment_text",
        ],
    )
    def test_known_callbacks_accepted(self, data: str):
        """Callback'ы редактора магазина пропущены."""
        assert embedding.is_admin_shop_callback(data) is True

    @pytest.mark.parametrize(
        "data",
        [
            None,
            "",
            # возврат в меню — перехватывает внешнее приложение
            "admin_main_menu",
            # заказы — не редактор магазина
            "admin_order_1",
            # платформенные/клиентские callback'ы
            "admin:test_shop",
            "client_start",
        ],
    )
    def test_foreign_callbacks_rejected(self, data: str | None):
        """Чужие callback'ы отклонены."""
        assert embedding.is_admin_shop_callback(data) is False
