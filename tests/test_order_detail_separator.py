"""Тесты длины разделителя блоков в карточке заказа (build_order_detail_text).

Когда чек оплаты — фото, карточка уходит caption под фото, где колонка уже,
поэтому разделитель должен быть короче, чтобы линия не переносилась на две строки.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from shopcrm_core.services.order_service import build_order_detail_text


def _fake_order(payment_proof_type=None, payment_proof=None) -> SimpleNamespace:
    """Минимальный объект заказа для build_order_detail_text."""
    return SimpleNamespace(
        id=42,
        user=SimpleNamespace(id=100, username="buyer"),
        items=[],
        delivery_price=0,
        total_price=10.0,
        delivery_address=None,
        delivery_address_type=None,
        user_comment=None,
        manager_comment=None,
        created_at=datetime(2026, 1, 1, 12, 0),
        is_paid=False,
        payment_proof_type=payment_proof_type,
        payment_proof=payment_proof,
        status="pending",
    )


def _make_repo(order) -> AsyncMock:
    repo = AsyncMock()
    repo.get_order_by_id = AsyncMock(return_value=order)
    return repo


def _separator_lengths(text: str) -> list[int]:
    """Длины всех строк-разделителей (строки, состоящие только из символов ━)."""
    return [len(line) for line in text.split("\n") if line and set(line) == {"━"}]


class TestOrderDetailSeparator:
    async def test_photo_proof_uses_short_separator(self):
        """Чек-фото → caption → короткий разделитель (12 символов) во всех 6 местах."""
        order = _fake_order(payment_proof_type="photo", payment_proof="https://x/y.jpg")
        text, _ = await build_order_detail_text(_make_repo(order), 42, lang="ru")
        assert _separator_lengths(text) == [12] * 6

    async def test_no_photo_uses_long_separator(self):
        """Без фото-чека → обычное сообщение → длинный разделитель (20 символов)."""
        order = _fake_order(payment_proof_type=None)
        text, _ = await build_order_detail_text(_make_repo(order), 42, lang="ru")
        assert _separator_lengths(text) == [20] * 6
