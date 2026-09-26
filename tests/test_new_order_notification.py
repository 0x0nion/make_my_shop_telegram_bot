"""Тесты уведомления администраторов о новом заказе (notify_admins_about_new_order).

Проверяют:
- сообщение уходит каждому админу на его сохранённом языке;
- в сообщении есть кнопка «Перейти к заказу» с callback ``admin_order_view:{order_id}``;
- ошибка отправки одному админу не блокирует остальных;
- при отсутствии заказа сообщения не отправляются.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from shopcrm_bot.services.notification_service import notify_admins_about_new_order


def _fake_order(order_id: int = 42) -> SimpleNamespace:
    """Минимальный объект заказа для build_order_detail_text."""
    return SimpleNamespace(
        id=order_id,
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
        payment_proof_type=None,
        payment_proof=None,
        status="pending",
    )


def _fake_admin(admin_id: int, language: str) -> SimpleNamespace:
    return SimpleNamespace(id=admin_id, language=language)


def _make_bot() -> AsyncMock:
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


def _make_repos(order: SimpleNamespace | None = None,
                admin_langs: dict[int, str] | None = None):
    """admin_repo / user_repo с нужным поведением."""
    admin_repo = AsyncMock()
    admin_repo.get_order_by_id = AsyncMock(return_value=order)
    admin_langs = admin_langs or {}
    user_repo = AsyncMock()
    user_repo.get_user = AsyncMock(
        side_effect=lambda admin_id: _fake_admin(admin_id, admin_langs.get(admin_id, "en"))
    )
    return admin_repo, user_repo


class TestNotifyAdminsAboutNewOrder:
    async def test_sends_message_to_each_admin_in_their_language(self):
        """Каждый админ получает уведомление на своём языке."""
        bot = _make_bot()
        admin_repo, user_repo = _make_repos(
            order=_fake_order(), admin_langs={1: "ru", 2: "en"}
        )

        await notify_admins_about_new_order(
            bot=bot, admin_repo=admin_repo, user_repo=user_repo,
            order_id=42, admin_ids=[1, 2],
        )

        assert bot.send_message.await_count == 2
        calls = {c.kwargs["chat_id"]: c.kwargs for c in bot.send_message.await_args_list}
        assert "НОВЫЙ ЗАКАЗ #42" in calls[1]["text"]
        assert "NEW ORDER #42" in calls[2]["text"]

    async def test_message_contains_open_order_button(self):
        """В уведомлении есть кнопка «Перейти к заказу» с корректным callback."""
        bot = _make_bot()
        admin_repo, user_repo = _make_repos(order=_fake_order())

        await notify_admins_about_new_order(
            bot=bot, admin_repo=admin_repo, user_repo=user_repo,
            order_id=42, admin_ids=[1],
        )

        markup = bot.send_message.await_args.kwargs["reply_markup"]
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        assert len(buttons) == 1
        assert buttons[0].callback_data == "admin_order_view:42"
        assert buttons[0].text == "📋 View order"

    async def test_button_text_localized(self):
        """Текст кнопки локализован под язык администратора."""
        bot = _make_bot()
        admin_repo, user_repo = _make_repos(order=_fake_order(), admin_langs={1: "ru"})

        await notify_admins_about_new_order(
            bot=bot, admin_repo=admin_repo, user_repo=user_repo,
            order_id=42, admin_ids=[1],
        )

        markup = bot.send_message.await_args.kwargs["reply_markup"]
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        assert buttons[0].text == "📋 Перейти к заказу"

    async def test_one_admin_failure_does_not_block_others(self):
        """Ошибка отправки первому админу не блокирует второго."""
        bot = _make_bot()
        bot.send_message = AsyncMock(side_effect=[RuntimeError("boom"), None])
        admin_repo, user_repo = _make_repos(order=_fake_order())

        await notify_admins_about_new_order(
            bot=bot, admin_repo=admin_repo, user_repo=user_repo,
            order_id=42, admin_ids=[1, 2],
        )

        assert bot.send_message.await_count == 2

    async def test_order_not_found_no_messages(self):
        """Заказ не найден — сообщения не отправляются."""
        bot = _make_bot()
        admin_repo, user_repo = _make_repos(order=None)

        await notify_admins_about_new_order(
            bot=bot, admin_repo=admin_repo, user_repo=user_repo,
            order_id=999, admin_ids=[1],
        )

        bot.send_message.assert_not_awaited()
