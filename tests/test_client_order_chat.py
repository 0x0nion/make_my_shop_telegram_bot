"""Тесты клиентского чата с менеджером по заказу.

Покрыто:
- кнопка «Написать менеджеру» в карточке заказа (скрыта для cancelled);
- открытие чата: история, FSM-состояние, открытие с последней страницы;
- чат закрыт для cancelled-заказов (защита от старых кнопок);
- не-текстовые сообщения не сохраняются в историю;
- текстовое сообщение сохраняется и админ уведомляется;
- сброс FSM-состояния при уходе из чата по навигации.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.cart import CartItem

from shopcrm_bot.handlers.client import order_reply as order_reply_module
from shopcrm_bot.handlers.client.order.order import _clear_reply_state
from shopcrm_bot.handlers.client.order_reply import (
    ClientReplyStates,
    client_send_reply,
    client_start_reply,
)
from shopcrm_bot.locales import Locale
from shopcrm_bot.services.chat_service import MESSAGES_PER_PAGE


async def _create_order(repo, session, user, product):
    """Вспомогательный: создаёт заказ для user через корзину."""
    session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
    await session.commit()
    order = await repo.create_order_from_cart(user_id=user.id)
    assert order is not None
    return order


def _callback(data: str) -> AsyncMock:
    """Фабрика мок-CallbackQuery."""
    cb = AsyncMock()
    cb.data = data
    cb.message.message_id = 42
    return cb


def _state() -> AsyncMock:
    """Фабрика мок-FSMContext."""
    st = AsyncMock()
    st.get_state.return_value = None
    st.get_data.return_value = {}
    return st


class TestOrderDetailKeyboard:
    """Кнопка «Написать менеджеру» в клавиатуре карточки заказа клиента."""

    def test_reply_button_shown_by_default(self):
        kb = Locale("ru").keyboards.get_client_order_detail_kb(order_id=7, cancellable=True)
        data = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "client_reply_order:7" in data

    def test_reply_button_hidden_for_cancelled(self):
        kb = Locale("ru").keyboards.get_client_order_detail_kb(
            order_id=7, cancellable=False, can_reply=False
        )
        data = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert not any(d and d.startswith("client_reply_order:") for d in data)
        # «Назад к списку» остаётся
        assert "client_orders" in data


class TestClientStartReply:
    """Открытие клиентского чата по заказу."""

    async def test_cancelled_order_chat_closed(self, repo, session, user_a, product_a):
        """Cancelled-заказ: alert, FSM-состояние не ставится."""
        order = await _create_order(repo, session, user_a, product_a)
        order.status = OrderStatus.CANCELLED.value
        await session.commit()

        cb = _callback(f"client_reply_order:{order.id}")
        st = _state()

        await client_start_reply(cb, st, repo, user_a)

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.kwargs.get("show_alert") is True
        st.set_state.assert_not_awaited()

    async def test_opens_last_page_and_sets_state(self, repo, session, user_a, product_a):
        """6 сообщений → чат открывается с последней страницы, FSM заполняется."""
        order = await _create_order(repo, session, user_a, product_a)
        order.chat_history = [
            {
                "sender": "admin" if i % 2 == 0 else "client",
                "text": f"msg-{i}",
                "time": f"t{i}",
            }
            for i in range(MESSAGES_PER_PAGE + 1)
        ]
        await session.commit()

        cb = _callback(f"client_reply_order:{order.id}")
        st = _state()
        shown = MagicMock()
        shown.message_id = 77

        with patch.object(
            order_reply_module.UIManager, "show", AsyncMock(return_value=shown)
        ) as mock_show:
            await client_start_reply(cb, st, repo, user_a)

        mock_show.assert_awaited_once()
        text = mock_show.await_args.kwargs["text"]
        # Последняя страница: самое свежее видно, самое старое — нет
        assert "msg-5" in text
        assert "msg-0" not in text
        st.set_state.assert_awaited_once_with(ClientReplyStates.waiting_for_reply)
        data = st.update_data.await_args.kwargs
        assert data["order_id"] == order.id
        assert data["main_message_id"] == 77

    async def test_foreign_order_rejected(self, repo, session, user_a, user_b, product_a):
        """Чужой заказ: alert, состояние не ставится."""
        order = await _create_order(repo, session, user_a, product_a)

        cb = _callback(f"client_reply_order:{order.id}")
        st = _state()

        await client_start_reply(cb, st, repo, user_b)

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.kwargs.get("show_alert") is True
        st.set_state.assert_not_awaited()


class TestClientSendReply:
    """Отправка сообщения клиентом в чат заказа."""

    async def test_non_text_message_not_saved(self, repo, session, user_a, product_a):
        """Фото/стикер (text=None): не сохраняется, показывается подсказка."""
        order = await _create_order(repo, session, user_a, product_a)

        message = AsyncMock()
        message.text = None
        message.from_user.id = user_a.id

        st = _state()
        st.get_data.return_value = {"order_id": order.id, "main_message_id": 55}

        with patch.object(order_reply_module.UIManager, "show", AsyncMock()) as mock_show:
            await client_send_reply(message, st, repo, user_a, admin_ids=[])

        mock_show.assert_awaited_once()
        assert "текстовое сообщение" in mock_show.await_args.kwargs["text"]
        st.clear.assert_awaited_once()

        fresh = await repo.get_order_with_items(order.id, user_a.id)
        assert not fresh.chat_history

    async def test_text_message_saved(self, repo, session, user_a, product_a):
        """Текст сохраняется в историю заказа с sender=client."""
        order = await _create_order(repo, session, user_a, product_a)

        message = AsyncMock()
        message.text = "hello"
        message.from_user.id = user_a.id
        message.bot = AsyncMock()

        st = _state()
        st.get_data.return_value = {"order_id": order.id, "main_message_id": 55}

        with patch.object(order_reply_module.UIManager, "show", AsyncMock()):
            await client_send_reply(message, st, repo, user_a, admin_ids=[])

        fresh = await repo.get_order_with_items(order.id, user_a.id)
        assert len(fresh.chat_history) == 1
        assert fresh.chat_history[0]["sender"] == "client"
        assert fresh.chat_history[0]["text"] == "hello"

    async def test_admin_notified_on_reply(self, repo, session, user_a, user_b, product_a):
        """Админ получает уведомление с кнопкой заказа."""
        order = await _create_order(repo, session, user_a, product_a)

        message = AsyncMock()
        message.text = "hello"
        message.from_user.id = user_a.id
        message.bot = AsyncMock()

        st = _state()
        st.get_data.return_value = {"order_id": order.id, "main_message_id": 55}

        with patch.object(order_reply_module.UIManager, "show", AsyncMock()):
            await client_send_reply(message, st, repo, user_a, admin_ids=[user_b.id])

        message.bot.send_message.assert_awaited_once()
        assert message.bot.send_message.await_args.kwargs["chat_id"] == user_b.id


class TestClearReplyState:
    """Сброс FSM-состояния ввода ответа при навигации."""

    async def test_clears_waiting_reply_state(self):
        st = _state()
        st.get_state.return_value = ClientReplyStates.waiting_for_reply.state

        await _clear_reply_state(st)

        st.clear.assert_awaited_once()

    async def test_keeps_other_states(self):
        st = _state()
        st.get_state.return_value = "some:other"

        await _clear_reply_state(st)

        st.clear.assert_not_awaited()
