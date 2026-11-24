# services/broadcast_sender.py
"""Фоновый отправщик рассылки (бот-приложение).

Отвечает за доставку сообщений и отказоустойчивость:

- БД — единственный источник истины: рассылка переживает рестарт бота,
  атомарный ``claim_running`` исключает двойную отправку;
- rate-limiter (RPS) + семафор параллельности — защита от 429 Telegram;
- классификация ошибок:
    * 403 (заблокировал бота), 400 «chat not found» (удалил чат),
      400 «deactivated» -> получатель ``blocked``, ``users.blocked_at``
      заполняется — недоступным больше не пишем (метка сбрасывается
      при следующей активности пользователя);
    * ``429`` -> ждём ``retry_after`` и повторяем;
    * сетевые сбои и 5xx -> повтор с линейным бэкоффом, затем ``failed``
      (рассылка продолжается дальше по списку);
- отметки коммитятся чанками: один сбой не роняет весь процесс;
- по завершении админ получает разовое уведомление с итогами.
"""
import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from shopcrm_core.db.models.broadcast import BroadcastStatus, RecipientStatus
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shopcrm_bot.locales import Locale

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class BroadcastSettings:
    """Настройки отправщика (из env-конфига бота)."""

    max_rps: float = 10.0
    concurrency: int = 10
    chunk_size: int = 50
    retry_attempts: int = 3
    retry_delay: float = 5.0

    @classmethod
    def from_config(cls, config) -> "BroadcastSettings":
        return cls(
            max_rps=config.BROADCAST_MAX_RPS,
            concurrency=config.BROADCAST_CONCURRENCY,
            chunk_size=config.BROADCAST_CHUNK_SIZE,
            retry_attempts=config.BROADCAST_RETRY_ATTEMPTS,
            retry_delay=config.BROADCAST_RETRY_DELAY,
        )


class _RateLimiter:
    """Выдаёт «слоты» отправки не чаще ``rps`` раз в секунду."""

    def __init__(self, rps: float):
        self._interval = 1.0 / rps if rps and rps > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    async def acquire(self) -> None:
        if self._interval <= 0:
            return
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval
        wait = slot - now
        if wait > 0:
            await asyncio.sleep(wait)


class BroadcastSender:
    """Отправка рассылки фоном: чанки, rate-limit, retry, отмена."""

    def __init__(
        self,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
        settings: BroadcastSettings | None = None,
    ):
        self._bot = bot
        self._session_factory = session_factory
        self._settings = settings or BroadcastSettings()
        self._limiter = _RateLimiter(self._settings.max_rps)
        self._semaphore = asyncio.Semaphore(self._settings.concurrency)
        self._tasks: dict[int, asyncio.Task] = {}

    # ==================== ПУБЛИЧНЫЙ API ====================

    def start(self, broadcast_id: int) -> bool:
        """Запустить фоновую задачу рассылки.

        :return: ``False``, если для этого ID уже есть живая задача
            (защита от двойного запуска по кнопке).
        """
        existing = self._tasks.get(broadcast_id)
        if existing and not existing.done():
            return False
        task = asyncio.create_task(self.run(broadcast_id), name=f"broadcast-{broadcast_id}")
        self._tasks[broadcast_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(broadcast_id, None))
        return True

    def is_running(self, broadcast_id: int) -> bool:
        task = self._tasks.get(broadcast_id)
        return bool(task and not task.done())

    async def shutdown(self) -> None:
        """Graceful-остановка: отменяет все фоновые задачи отправки.

        Вызывается при shutdown бота (до закрытия БД). Незавершённые
        рассылки остаются в БД (running) и помечаются ``interrupted``
        вызывающим кодом — после рестарта их можно возобновить.
        """
        tasks = [t for t in self._tasks.values() if not t.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()

    async def run(self, broadcast_id: int) -> None:
        """Основной цикл рассылки (вызывается как фоновая задача)."""
        # 1. Атомарный claim: pending/interrupted -> running.
        #    Если кто-то уже отправляет — тихо выходим.
        async with self._session_factory() as session:
            repo = AdminRepository(session)
            if not await repo.claim_running(broadcast_id):
                # Отмена пришла до claim (рассылка ещё не стартовала) —
                # финализируем, чтобы статус не завис в «cancelling».
                current = await repo.get_broadcast(broadcast_id)
                if current and current.status == BroadcastStatus.CANCELLING.value:
                    await self._finalize(session, broadcast_id, cancelled=True)
                    await self._notify_admin(broadcast_id)
                return
            broadcast = await repo.get_broadcast(broadcast_id)
            if broadcast is None:
                return
            text = broadcast.text

        logger.info(f"Broadcast {broadcast_id} started: {broadcast.total} recipients")

        # 2. Отправка чанками.
        while True:
            async with self._session_factory() as session:
                repo = AdminRepository(session)
                current = await repo.get_broadcast(broadcast_id)
                if current is None:
                    return
                if current.status == BroadcastStatus.CANCELLING.value:
                    await self._finalize(session, broadcast_id, cancelled=True)
                    await self._notify_admin(broadcast_id)
                    return
                if current.status != BroadcastStatus.RUNNING.value:
                    # Уже завершена кем-то другим — выходим
                    return
                chunk = await repo.get_pending_recipients(
                    broadcast_id, limit=self._settings.chunk_size
                )
                if not chunk:
                    break
                chunk_data = [(r.id, r.user_id) for r in chunk]

            results = await self._send_chunk(chunk_data, text)

            async with self._session_factory() as session:
                repo = AdminRepository(session)
                for recipient_id, user_id, status, attempts, error in results:
                    await repo.mark_recipient(recipient_id, status, attempts, error)
                    if status == RecipientStatus.BLOCKED.value:
                        await repo.mark_user_blocked(user_id)
                await session.commit()
                await repo.refresh_counters(broadcast_id)

        # 3. Финализация.
        finalized = False
        async with self._session_factory() as session:
            repo = AdminRepository(session)
            current = await repo.get_broadcast(broadcast_id)
            if current is None:
                return
            if current.status == BroadcastStatus.RUNNING.value:
                await self._finalize(session, broadcast_id, cancelled=False)
                finalized = True
            elif current.status == BroadcastStatus.CANCELLING.value:
                # Отмена пришла в самый последний момент
                await self._finalize(session, broadcast_id, cancelled=True)
                finalized = True

        # 4. Разовое уведомление админу о завершении (только если
        #    финализировали мы — иначе уведомит другой процесс).
        if finalized:
            await self._notify_admin(broadcast_id)

    # ==================== ВНУТРЕННЕЕ ====================

    async def _finalize(self, session: AsyncSession, broadcast_id: int, cancelled: bool) -> None:
        repo = AdminRepository(session)
        await repo.refresh_counters(broadcast_id)
        status = (
            BroadcastStatus.CANCELLED.value if cancelled else BroadcastStatus.COMPLETED.value
        )
        await repo.set_status(broadcast_id, status, finished_at=_utcnow())
        logger.info(f"Broadcast {broadcast_id} finalized: {status}")

    async def _notify_admin(self, broadcast_id: int) -> None:
        """Разовое уведомление создавшему админу: итоги рассылки.

        Ошибка уведомления не влияет на статус рассылки (она уже
        финализирована) — только лог.
        """
        try:
            async with self._session_factory() as session:
                broadcast = await AdminRepository(session).get_broadcast(broadcast_id)
                if broadcast is None:
                    return
                admin = await session.get(User, broadcast.admin_id)
                lang = admin.language if admin else "en"
            locale = Locale(lang=lang)
            text = locale.get_text(
                "admin.broadcast.done_notification",
                sent=broadcast.sent,
                failed=broadcast.failed,
                blocked=broadcast.blocked,
            )
            await self._bot.send_message(broadcast.admin_id, text)
            logger.info(f"Broadcast {broadcast_id}: admin {broadcast.admin_id} notified")
        except Exception:
            logger.exception(f"Broadcast {broadcast_id}: failed to notify admin")

    async def _send_chunk(self, chunk_data: list[tuple[int, int]], text: str) -> list[tuple]:
        """Отправить чанк параллельно (семафор + rate-limiter)."""

        async def _one(recipient_id: int, user_id: int) -> tuple:
            async with self._semaphore:
                await self._limiter.acquire()
                status, attempts, error = await self._send_one(user_id, text)
                return recipient_id, user_id, status, attempts, error

        return list(await asyncio.gather(*(_one(rid, uid) for rid, uid in chunk_data)))

    async def _send_one(self, user_id: int, text: str) -> tuple[str, int, str | None]:
        """Отправить одно сообщение с retry. Возвращает (status, attempts, error).

        Классификация:
          - 403 (заблокировал бота), 400 «chat not found» (удалил чат),
            400 «deactivated» -> BLOCKED: пользователь недоступен,
            ``users.blocked_at`` заполняется, повторов не будет;
          - 429 -> ждём retry_after и повторяем;
          - сетевые сбои и 5xx (транзитные) -> повтор с бэкоффом, затем FAILED;
          - прочие 4xx -> FAILED (повторять бессмысленно).
        """
        max_attempts = max(1, self._settings.retry_attempts)
        for attempt in range(1, max_attempts + 1):
            try:
                await self._bot.send_message(user_id, text)
                return RecipientStatus.SENT.value, attempt, None
            except TelegramRetryAfter as e:
                # 429: уважаем retry_after от Telegram
                if attempt >= max_attempts:
                    return RecipientStatus.FAILED.value, attempt, "retry_after exceeded"
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError as e:
                # 403: пользователь заблокировал бота — недоступен, повторов не будет
                return RecipientStatus.BLOCKED.value, attempt, str(e)
            except TelegramBadRequest as e:
                msg = str(e).lower()
                if (
                    "chat not found" in msg
                    or "deactivated" in msg
                    or "blocked" in msg
                    or "forbidden" in msg
                ):
                    # Удалил чат бота / деактивирован / заблокировал — недоступен
                    return RecipientStatus.BLOCKED.value, attempt, str(e)
                if "not modified" in msg:
                    return RecipientStatus.SENT.value, attempt, None
                # Прочие 4xx — повторять бессмысленно
                return RecipientStatus.FAILED.value, attempt, str(e)
            except (TelegramNetworkError, TelegramServerError) as e:
                # Транзитный сбой (сеть / серверы Telegram) — повтор с бэкоффом
                if attempt >= max_attempts:
                    return RecipientStatus.FAILED.value, attempt, str(e)
                await asyncio.sleep(self._settings.retry_delay * attempt)
            except TelegramAPIError as e:
                # Неожиданный API-ответ — не роняем рассылку
                return RecipientStatus.FAILED.value, attempt, str(e)
        return RecipientStatus.FAILED.value, max_attempts, "max attempts exceeded"

