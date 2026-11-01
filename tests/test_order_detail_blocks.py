"""Тесты структуры карточки заказа администратора (build_order_detail_text).

Проверяют:
- 4 блока: (дата/статус/комментарий менеджера) | (покупатель/адрес/комментарий
  клиента/чек) | (состав заказа) | (расчёт стоимости);
- покупатель отображается как номер ID со ссылкой на пользователя;
- пустые поля показываются единым плейсхолдером «Пусто».
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from shopcrm_core.services.order_service import build_order_detail_text

_SEPARATOR = "━" * 20
_UNSET = object()


def _fake_order(user=_UNSET, **overrides) -> SimpleNamespace:
    """Минимальный объект заказа для build_order_detail_text."""
    if user is _UNSET:
        user = SimpleNamespace(id=100, username="buyer")
    order = SimpleNamespace(
        id=42,
        user=user,
        items=[],
        delivery_price=0,
        total_price=10.0,
        delivery_address=None,
        delivery_address_type=None,
        user_comment=None,
        manager_comment=None,
        created_at=datetime(2026, 1, 1, 12, 0),
        is_paid=False,
        payment_proof_type=None,
        payment_proof=None,
        status="pending",
    )
    for key, value in overrides.items():
        setattr(order, key, value)
    return order


def _make_repo(order) -> AsyncMock:
    repo = AsyncMock()
    repo.get_order_by_id = AsyncMock(return_value=order)
    return repo


async def _build(order, lang: str = "ru") -> str:
    text, _ = await build_order_detail_text(_make_repo(order), 42, lang=lang)
    return text


class TestOrderDetailBlocks:
    async def test_four_blocks_in_order(self):
        """Карточка состоит из 4 блоков в заданном порядке."""
        text = await _build(_fake_order())
        blocks = text.split(_SEPARATOR)
        assert len(blocks) == 4

        # Блок 1: заказ, дата, статус, комментарий менеджера
        assert "Заказ #42" in blocks[0]
        assert "Дата" in blocks[0]
        assert "Статус" in blocks[0]
        assert "Комментарий менеджера" in blocks[0]

        # Блок 2: покупатель, адрес, комментарий клиента, чек
        assert "Покупатель" in blocks[1]
        assert "Адрес доставки" in blocks[1]
        assert "Комментарий клиента" in blocks[1]
        assert "Подтверждение оплаты" in blocks[1]

        # Блок 3: состав заказа
        assert "Состав заказа" in blocks[2]

        # Блок 4: расчёт стоимости
        assert "Расчёт стоимости" in blocks[3]
        assert "Итого к оплате" in blocks[3]

    async def test_block_order_by_position(self):
        """Блоки идут строго в порядке: менеджер → покупатель → корзина → стоимость."""
        text = await _build(_fake_order())
        assert (
            text.index("Комментарий менеджера")
            < text.index("Покупатель")
            < text.index("Состав заказа")
            < text.index("Расчёт стоимости")
        )

    async def test_total_price_two_decimals(self):
        """Сумма в блоке стоимости показывается минимум с двумя знаками."""
        text = await _build(_fake_order())
        blocks = text.split(_SEPARATOR)
        assert "10.00" in blocks[3]


class TestOrderDetailBuyer:
    async def test_buyer_is_id_link(self):
        """Покупатель — номер ID со ссылкой на пользователя."""
        text = await _build(_fake_order())
        assert '<a href="tg://user?id=100">100</a>' in text

    async def test_buyer_without_user_is_empty(self):
        """Нет записи пользователя — плейсхолдер «Пусто»."""
        text = await _build(_fake_order(user=None))
        assert "Пусто" in text
        assert "tg://user" not in text


class TestOrderDetailEmptyFields:
    async def test_empty_fields_show_placeholder(self):
        """Пустые адрес, комментарии и чек показываются как «Пусто»."""
        text = await _build(_fake_order())
        assert text.count("Пусто") == 4

    async def test_filled_fields_show_values(self):
        """Заполненные поля показываются вместо плейсхолдера."""
        order = _fake_order(
            delivery_address="Москва, ул. Ленина, 1",
            delivery_address_type="address",
            user_comment="коммент клиента",
            manager_comment="коммент менеджера",
            payment_proof_type="cash",
        )
        text = await _build(order)
        assert "Москва, ул. Ленина, 1" in text
        assert "коммент клиента" in text
        assert "коммент менеджера" in text
        assert "Пусто" not in text


class TestOrderDetailStatusLocalization:
    """Статус в карточке — локализованная подпись, а не сырое значение."""

    @pytest.mark.parametrize("lang, expected", [
        ("ru", "Создан / Ожидает"),
        ("en", "Pending"),
        ("es", "Pendientes"),
    ])
    async def test_status_label_localized(self, lang, expected):
        text = await _build(_fake_order(status="pending"), lang=lang)
        assert expected in text

    async def test_raw_status_not_shown(self):
        """Сырое значение 'pending' в карточке не отображается."""
        text = await _build(_fake_order(status="pending"))
        assert "pending" not in text
