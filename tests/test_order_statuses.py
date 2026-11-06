"""Тесты системы статусов заказа (OrderStatus и производные константы).

Проверяют:
- у каждого статуса есть уникальный короткий код для callback_data;
- ORDER_STATUS_BY_CODE — точное обратное отображение;
- меню фильтров админа покрывает все статусы (и только валидные);
- у каждого статуса есть локализованная подпись на всех 3 языках;
- callback смены статуса не превышает лимит Telegram в 64 байта.
"""
import pytest
from shopcrm_core.constants import (
    ADMIN_ORDER_STATUS_FILTERS,
    ORDER_STATUS_BY_CODE,
    ORDER_STATUS_CODES,
    ORDER_STATUS_VALUES,
    OrderStatus,
)
from shopcrm_core.locales.locale import Locale


class TestStatusCodes:
    """Короткие коды статусов для callback_data."""

    def test_every_status_has_a_code(self):
        assert set(ORDER_STATUS_CODES) == ORDER_STATUS_VALUES

    def test_codes_are_unique(self):
        codes = list(ORDER_STATUS_CODES.values())
        assert len(codes) == len(set(codes))

    def test_by_code_is_reverse_mapping(self):
        assert {v: k for k, v in ORDER_STATUS_CODES.items()} == ORDER_STATUS_BY_CODE


class TestAdminFilters:
    """ADMIN_ORDER_STATUS_FILTERS — единый источник истины для меню фильтров."""

    def test_all_filters_map_to_valid_statuses(self):
        for callback_key, status in ADMIN_ORDER_STATUS_FILTERS.items():
            assert status in ORDER_STATUS_VALUES, callback_key

    def test_every_status_has_a_filter(self):
        assert set(ADMIN_ORDER_STATUS_FILTERS.values()) == ORDER_STATUS_VALUES

    def test_filter_order_follows_lifecycle(self):
        """Основной жизненный цикл — сверху, побочные состояния — в конце."""
        keys = list(ADMIN_ORDER_STATUS_FILTERS)
        assert keys[:8] == [
            "admin_order_pending",
            "admin_order_payment_requested",
            "admin_order_awaiting",
            "admin_order_payment_rejected",
            "admin_order_processing",
            "admin_order_ready",
            "admin_order_delivering",
            "admin_order_completed",
        ]
        assert keys[8:] == ["admin_order_cancelled", "admin_order_on_hold", "admin_order_refund"]


class TestStatusLabels:
    """Локализованные подписи статусов (keyboards.admin.order_status_menu)."""

    @pytest.mark.parametrize("lang", ["ru", "en", "es"])
    @pytest.mark.parametrize("status", list(OrderStatus))
    def test_label_exists_in_all_languages(self, lang, status):
        label = Locale(lang).get_order_status_label(status.value)
        # Не пустая и не fallback на сырое значение статуса.
        assert label and label != status.value


class TestCallbackDataLimit:
    """Лимит Telegram на callback_data — 64 байта."""

    def test_set_status_callback_fits_limit(self):
        """Худший случай: большой ID заказа + двухзначные коды новых статусов."""
        order_id = 99_999_999
        worst_code = max(ORDER_STATUS_CODES.values(), key=len)
        data = f"admin_order_set_status:{order_id}:{worst_code}:{worst_code}:99"
        assert len(data.encode("utf-8")) <= 64


class TestFinalStatuses:
    """is_final — только completed и cancelled."""

    def test_final_statuses(self):
        assert OrderStatus.is_final(OrderStatus.COMPLETED.value)
        assert OrderStatus.is_final(OrderStatus.CANCELLED.value)

    @pytest.mark.parametrize(
        "status", [s for s in OrderStatus if s not in (OrderStatus.COMPLETED, OrderStatus.CANCELLED)]
    )
    def test_non_final_statuses(self, status):
        assert not OrderStatus.is_final(status.value)