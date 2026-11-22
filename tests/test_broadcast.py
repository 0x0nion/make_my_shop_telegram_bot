"""Тесты рассылки (broadcast): снапшот, сервис, отказоустойчивость отправщика.

Отправщик тестируется на реальной in-memory БД (StaticPool — одно
подключение на все сессии; в отправщике сессии строго последовательны)
и фейковом боте (классификация ошибок Telegram).
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest_asyncio
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from shopcrm_bot.services.broadcast_sender import BroadcastSender, BroadcastSettings
from shopcrm_core.db.models.base import Base
from shopcrm_core.db.models.broadcast import BroadcastRecipient
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.services.broadcast_service import BroadcastService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _make_user(session: AsyncSession, user_id: int, role: str = "client", blocked_at=None) -> User:
    user = User(id=user_id, language="ru", role=role, blocked_at=blocked_at)
    session.add(user)
    return user


def _raise(exc: Exception):
    """Хелпер для FakeBot: поведение, которое всегда бросает исключение."""

    def handler(attempt: int) -> None:
        raise exc

    return handler


class FakeBot:
    """Фейк бота: поведение send_message настраивается per user_id."""

    def __init__(self, behavior: dict | None = None):
        # behavior: user_id -> callable(attempt) — может бросить исключение
        self.behavior = behavior or {}
        self.sent: list[tuple[int, str]] = []
        self.attempts: dict[int, int] = {}

    async def send_message(self, user_id: int, text: str):
        self.attempts[user_id] = self.attempts.get(user_id, 0) + 1
        handler = self.behavior.get(user_id)
        if handler:
            handler(self.attempts[user_id])
        self.sent.append((user_id, text))


# ==================== Фикстуры (много-сессионная in-memory БД) ====================

@pytest_asyncio.fixture
async def broadcast_engine():
    """In-memory SQLite с единым подключением (StaticPool).

    Отправщик создаёт несколько сессий (по одной на чанк) — с обычным
    in-memory SQLite они бы видели разные БД. StaticPool делит одно
    подключение, что корректно, т.к. сессии в отправщике последовательны.
    """
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(broadcast_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(broadcast_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def repo(session_factory) -> AdminRepository:
    async with session_factory() as session:
        yield AdminRepository(session)


async def _create_broadcast(session_factory, user_ids: list[int], admin_id: int = 1) -> int:
    """Создать пользователей + pending-рассылку. Возвращает broadcast_id."""
    async with session_factory() as session:
        for uid in user_ids:
            _make_user(session, uid)
        await session.commit()
        r = AdminRepository(session)
        b = await r.create_broadcast(admin_id=admin_id, text="hello", total=len(user_ids), skipped=0)
        await r.create_recipients(b.id, user_ids)
        return b.id


def _settings(**overrides) -> BroadcastSettings:
    base = dict(max_rps=0, concurrency=2, chunk_size=2, retry_attempts=3, retry_delay=0.01)
    base.update(overrides)
    return BroadcastSettings(**base)


# ==================== СНАПШОТ ПОЛУЧАТЕЛЕЙ ====================

class TestSnapshot:
    async def test_excludes_admins_blocked_and_role_admin(self, repo, session_factory):
        async with session_factory() as session:
            _make_user(session, 100)  # обычный
            _make_user(session, 200)  # обычный
            _make_user(session, 300, role="admin")  # роль админа
            _make_user(session, 400, blocked_at=_utcnow())  # заблокировал бота
            await session.commit()
        ids = await repo.snapshot_recipients(admin_ids=[100])
        assert ids == [200]

    async def test_cooldown_excludes_recently_sent(self, repo, session_factory):
        async with session_factory() as session:
            _make_user(session, 100)
            _make_user(session, 200)
            await session.commit()
            r = AdminRepository(session)
            b = await r.create_broadcast(admin_id=1, text="hi", total=2, skipped=0)
            await r.create_recipients(b.id, [100, 200])
            rec = await session.scalar(
                select(BroadcastRecipient).where(
                    BroadcastRecipient.broadcast_id == b.id,
                    BroadcastRecipient.user_id == 100,
                )
            )
            await r.mark_recipient(rec.id, "sent")
            await session.commit()
        # 100 уже получил рассылку в окне cooldown — исключается
        ids = await repo.snapshot_recipients(
            admin_ids=[], cooldown_since=_utcnow() - timedelta(hours=1)
        )
        assert ids == [200]
        # Без cooldown — оба
        ids = await repo.snapshot_recipients(admin_ids=[])
        assert ids == [100, 200]


# ==================== СЕРВИС ====================

class TestBroadcastService:
    async def test_create_empty_text(self, session_factory):
        async with session_factory() as session:
            service = BroadcastService(AdminRepository(session), 24.0)
            result = await service.create(1, "   ", [])
        assert result.error == "empty_text"
        assert result.broadcast is None

    async def test_create_no_recipients(self, session_factory):
        async with session_factory() as session:
            service = BroadcastService(AdminRepository(session), 24.0)
            result = await service.create(1, "text", [])
        assert result.error == "no_recipients"

    async def test_create_already_active(self, session_factory):
        await _create_broadcast(session_factory, [100])
        async with session_factory() as session:
            service = BroadcastService(AdminRepository(session), 24.0)
            result = await service.create(1, "text", [])
        assert result.error == "already_active"

    async def test_create_success(self, session_factory):
        async with session_factory() as session:
            _make_user(session, 100)
            _make_user(session, 200)
            _make_user(session, 300, blocked_at=_utcnow())
            await session.commit()
            service = BroadcastService(AdminRepository(session), 24.0)
            result = await service.create(1, "hello", [1])
        assert result.error is None
        assert result.recipients == 2
        assert result.skipped == 1  # заблокированный
        assert result.broadcast.status == "pending"
        async with session_factory() as session:
            r = AdminRepository(session)
            counts = await r.count_recipients(result.broadcast.id)
            assert counts["pending"] == 2

    async def test_cancel_running(self, session_factory):
        bid = await _create_broadcast(session_factory, [100])
        async with session_factory() as session:
            r = AdminRepository(session)
            await r.set_status(bid, "running", started_at=_utcnow())
            service = BroadcastService(AdminRepository(session), 24.0)
            status = await service.cancel(1, bid)
        assert status == "cancelled"
        async with session_factory() as session:
            b = await AdminRepository(session).get_broadcast(bid)
            assert b.status == "cancelling"

    async def test_cancel_not_found(self, session_factory):
        async with session_factory() as session:
            service = BroadcastService(AdminRepository(session), 24.0)
            assert await service.cancel(1, 999) == "not_found"

    async def test_delete_pending(self, session_factory):
        bid = await _create_broadcast(session_factory, [100])
        async with session_factory() as session:
            service = BroadcastService(AdminRepository(session), 24.0)
            assert await service.delete_pending(1, bid) is True
            assert await service.delete_pending(1, bid) is False  # уже удалена
            b = await AdminRepository(session).get_broadcast(bid)
            assert b is None


# ==================== ОТПРАВИТЕЛЬ (отказоустойчивость) ====================

class TestBroadcastSender:
    async def test_full_run_all_sent(self, session_factory):
        bid = await _create_broadcast(session_factory, [100, 200, 300])
        bot = FakeBot()
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)

        async with session_factory() as session:
            r = AdminRepository(session)
            b = await r.get_broadcast(bid)
            assert b.status == "completed"
            assert b.sent == 3
            assert b.failed == 0
            assert b.blocked == 0
        assert sorted(u for u, _ in bot.sent) == [100, 200, 300]

    async def test_blocked_user_marked_and_no_repeat(self, session_factory):
        bid = await _create_broadcast(session_factory, [100, 200])
        bot = FakeBot(behavior={
            100: _raise(TelegramBadRequest(method=MagicMock(), message="blocked by the user")),
        })
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)

        async with session_factory() as session:
            r = AdminRepository(session)
            b = await r.get_broadcast(bid)
            assert b.status == "completed"
            assert b.sent == 1
            assert b.blocked == 1
            # Пользователь помечен заблокированным (повторов не будет)
            user = await session.get(User, 100)
            assert user.blocked_at is not None
        # 100 не отправляли повторно, 200 — доставили
        assert sorted(u for u, _ in bot.sent) == [200]
        assert bot.attempts[100] == 1  # blocked — без повторов

    async def test_429_retried_then_sent(self, session_factory):
        bid = await _create_broadcast(session_factory, [100])
        calls = {"n": 0}

        def handler(attempt: int) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TelegramRetryAfter(method=MagicMock(), message="429", retry_after=0)

        bot = FakeBot(behavior={100: handler})
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)

        async with session_factory() as session:
            b = await AdminRepository(session).get_broadcast(bid)
            assert b.status == "completed"
            assert b.sent == 1
        assert calls["n"] == 2  # первый раз 429, второй — успех

    async def test_network_error_failed_but_broadcast_continues(self, session_factory):
        bid = await _create_broadcast(session_factory, [100, 200])
        bot = FakeBot(behavior={
            100: _raise(TelegramNetworkError(method=MagicMock(), message="connection error")),
        })
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)

        async with session_factory() as session:
            b = await AdminRepository(session).get_broadcast(bid)
            assert b.status == "completed"  # рассылка не упала
            assert b.sent == 1  # 200 доставлен
            assert b.failed == 1  # 100 после исчерпания повторов
        assert bot.attempts[100] == 3  # retry_attempts
        assert sorted(u for u, _ in bot.sent) == [200]

    async def test_cancel_before_claim_finalizes(self, session_factory):
        """Отмена до claim (рассылка ещё не стартовала) — статус не висит."""
        bid = await _create_broadcast(session_factory, [100, 200])
        async with session_factory() as session:
            await AdminRepository(session).set_status(bid, "cancelling")
        bot = FakeBot()
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)

        async with session_factory() as session:
            b = await AdminRepository(session).get_broadcast(bid)
            assert b.status == "cancelled"
        assert bot.sent == []

    async def test_claim_prevents_double_run(self, session_factory):
        bid = await _create_broadcast(session_factory, [100])
        bot = FakeBot()
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)
        await sender.run(bid)  # вторая попытка: claim не проходит
        assert len(bot.sent) == 1  # дублей нет

    async def test_resume_after_interrupt(self, session_factory):
        """Прерванная рассылка: отправляются только не отправленные."""
        bid = await _create_broadcast(session_factory, [100, 200, 300])
        # Имитируем частичный прогресс + крах: 100 отправлен, статус interrupted
        async with session_factory() as session:
            r = AdminRepository(session)
            rec = await session.scalar(
                select(BroadcastRecipient).where(
                    BroadcastRecipient.broadcast_id == bid,
                    BroadcastRecipient.user_id == 100,
                )
            )
            await r.mark_recipient(rec.id, "sent")
            await r.set_status(bid, "interrupted", started_at=_utcnow())
            await session.commit()

        bot = FakeBot()
        sender = BroadcastSender(bot, session_factory, _settings())
        await sender.run(bid)

        async with session_factory() as session:
            b = await AdminRepository(session).get_broadcast(bid)
            assert b.status == "completed"
            assert b.sent == 3
        # 100 не отправляли повторно
        assert sorted(u for u, _ in bot.sent) == [200, 300]

    async def test_interrupt_orphans(self, session_factory):
        bid = await _create_broadcast(session_factory, [100])
        async with session_factory() as session:
            await AdminRepository(session).set_status(bid, "running", started_at=_utcnow())
        async with session_factory() as session:
            r = AdminRepository(session)
            ids = await r.interrupt_orphans()
            assert bid in ids
            b = await r.get_broadcast(bid)
            assert b.status == "interrupted"

    async def test_resumable_only_fresh(self, session_factory):
        bid = await _create_broadcast(session_factory, [100])
        async with session_factory() as session:
            r = AdminRepository(session)
            # Свежая прерванная — возобновляется
            await r.set_status(bid, "interrupted", started_at=_utcnow())
            fresh = await r.get_resumable_broadcasts(24.0)
            assert [b.id for b in fresh] == [bid]
            # Старая (25 ч назад) — нет
            await r.set_status(bid, "interrupted", started_at=_utcnow() - timedelta(hours=25))
            old = await r.get_resumable_broadcasts(24.0)
            assert old == []



