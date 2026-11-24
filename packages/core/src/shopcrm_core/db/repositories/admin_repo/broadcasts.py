# db/repositories/admin_repo/broadcasts.py
"""Репозиторий рассылки (broadcast).

БД — единственный источник истины: снапшот получателей, атомарный
claim (защита от двойного запуска), чанки pending, отметки, финализация,
прерывание «осиротевших» рассылок после рестарта бота.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shopcrm_core.db.models.broadcast import Broadcast, BroadcastRecipient, BroadcastStatus, RecipientStatus
from shopcrm_core.db.models.user import User


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AdminBroadcastsMixin:
    """Методы рассылки для AdminRepository."""

    # ==================== СНАПШОТ ПОЛУЧАТЕЛЕЙ ====================

    async def snapshot_recipients(
        self,
        admin_ids: list[int],
        cooldown_since: datetime | None = None,
    ) -> list[int]:
        """ID получателей рассылки.

        Все пользователи, кроме:
          - администраторов (env + работники + role='admin');
          - заблокировавших бота (``blocked_at``);
          - тех, кому уже отправляли в окне cooldown (``cooldown_since``).
        """
        stmt = select(User.id).where(
            User.blocked_at.is_(None),
            User.role != "admin",
        )
        if admin_ids:
            stmt = stmt.where(User.id.not_in(admin_ids))
        if cooldown_since is not None:
            recent_sent = (
                select(BroadcastRecipient.user_id)
                .join(Broadcast, Broadcast.id == BroadcastRecipient.broadcast_id)
                .where(
                    BroadcastRecipient.status == RecipientStatus.SENT.value,
                    Broadcast.created_at >= cooldown_since,
                )
            )
            stmt = stmt.where(User.id.not_in(recent_sent))
        result = await self.session.execute(stmt.order_by(User.id))
        return [row[0] for row in result.all()]

    async def count_active_users(self) -> int:
        """Всего пользователей (для расчёта «пропущено» в UI)."""
        return await self.session.scalar(select(func.count()).select_from(User)) or 0

    # ==================== РАССЫЛКА ====================

    async def create_broadcast(self, admin_id: int, text: str, total: int, skipped: int) -> Broadcast:
        broadcast = Broadcast(
            admin_id=admin_id,
            text=text,
            status=BroadcastStatus.PENDING.value,
            total=total,
            skipped=skipped,
            created_at=_utcnow(),
        )
        self.session.add(broadcast)
        await self.session.flush()
        return broadcast

    async def create_recipients(self, broadcast_id: int, user_ids: list[int]) -> int:
        """Пакетное создание снапшота получателей (чанками по 500)."""
        chunk_size = 500
        for i in range(0, len(user_ids), chunk_size):
            chunk = user_ids[i:i + chunk_size]
            if self.session.bind.dialect.name == "postgresql":
                stmt = pg_insert(BroadcastRecipient).values(
                    [
                        {"broadcast_id": broadcast_id, "user_id": uid, "status": RecipientStatus.PENDING.value}
                        for uid in chunk
                    ]
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=["broadcast_id", "user_id"])
                await self.session.execute(stmt)
            else:
                for uid in chunk:
                    self.session.add(
                        BroadcastRecipient(
                            broadcast_id=broadcast_id,
                            user_id=uid,
                            status=RecipientStatus.PENDING.value,
                        )
                    )
        await self.session.commit()
        return len(user_ids)

    async def get_broadcast(self, broadcast_id: int) -> Broadcast | None:
        return await self.session.scalar(select(Broadcast).where(Broadcast.id == broadcast_id))

    async def get_latest_broadcast(self, admin_id: int) -> Broadcast | None:
        return await self.session.scalar(
            select(Broadcast)
            .where(Broadcast.admin_id == admin_id)
            .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
            .limit(1)
        )

    async def get_active_broadcast(self) -> Broadcast | None:
        """Активная рассылка магазина (pending/running/cancelling).

        Per-shop: пока идёт любая рассылка, новую запустить нельзя.
        """
        return await self.session.scalar(
            select(Broadcast)
            .where(
                Broadcast.status.in_(
                    [
                        BroadcastStatus.PENDING.value,
                        BroadcastStatus.RUNNING.value,
                        BroadcastStatus.CANCELLING.value,
                    ]
                ),
            )
            .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
            .limit(1)
        )

    async def claim_running(self, broadcast_id: int) -> bool:
        """Атомарный запуск: pending/interrupted -> running.

        Гарантирует, что рассылку отправляет только одна задача
        (даже при гонке «рестарт + авто-возобновление»).
        """
        result = await self.session.execute(
            update(Broadcast)
            .where(
                Broadcast.id == broadcast_id,
                Broadcast.status.in_(
                    [BroadcastStatus.PENDING.value, BroadcastStatus.INTERRUPTED.value]
                ),
            )
            .values(status=BroadcastStatus.RUNNING.value, started_at=_utcnow())
        )
        await self.session.commit()
        return (result.rowcount or 0) > 0

    async def set_status(self, broadcast_id: int, status: str, **fields) -> None:
        values: dict = {"status": status}
        values.update(fields)
        await self.session.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(**values))
        await self.session.commit()

    # ==================== ПОЛУЧАТЕЛИ ====================

    async def get_pending_recipients(self, broadcast_id: int, limit: int) -> list[BroadcastRecipient]:
        result = await self.session.execute(
            select(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status.in_(
                    [RecipientStatus.PENDING.value, RecipientStatus.RETRY_ASYNC.value]
                ),
            )
            .order_by(BroadcastRecipient.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_recipient(
        self,
        recipient_id: int,
        status: str,
        attempts: int | None = None,
        last_error: str | None = None,
    ) -> None:
        values: dict = {"status": status, "updated_at": _utcnow()}
        if attempts is not None:
            values["attempts"] = attempts
        if last_error is not None:
            values["last_error"] = last_error[:500]
        await self.session.execute(
            update(BroadcastRecipient).where(BroadcastRecipient.id == recipient_id).values(**values)
        )

    async def mark_user_blocked(self, user_id: int) -> None:
        """Пользователь заблокировал бота — помечаем, чтобы не писать повторно."""
        await self.session.execute(
            update(User).where(User.id == user_id, User.blocked_at.is_(None)).values(blocked_at=_utcnow())
        )

    async def count_recipients(self, broadcast_id: int) -> dict[str, int]:
        """Счётчики получателей по статусам (для прогресса и финализации)."""
        result = await self.session.execute(
            select(BroadcastRecipient.status, func.count())
            .where(BroadcastRecipient.broadcast_id == broadcast_id)
            .group_by(BroadcastRecipient.status)
        )
        counts = {status.value: 0 for status in RecipientStatus}
        for status, count in result.all():
            counts[status] = count
        return counts

    async def refresh_counters(self, broadcast_id: int) -> None:
        """Обновить счётчики рассылки из фактических статусов получателей."""
        counts = await self.count_recipients(broadcast_id)
        await self.session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(
                sent=counts[RecipientStatus.SENT.value],
                failed=counts[RecipientStatus.FAILED.value],
                blocked=counts[RecipientStatus.BLOCKED.value],
            )
        )
        await self.session.commit()

    # ==================== РЕСТАРТ / ВОЗОБНОВЛЕНИЕ ====================

    async def interrupt_orphans(self) -> list[int]:
        """running -> interrupted (бот упал/перезапустился). Возвращает ID."""
        result = await self.session.execute(
            update(Broadcast)
            .where(Broadcast.status == BroadcastStatus.RUNNING.value)
            .values(status=BroadcastStatus.INTERRUPTED.value, finished_at=_utcnow())
        )
        await self.session.commit()
        if not result.rowcount:
            return []
        ids_result = await self.session.execute(
            select(Broadcast.id).where(Broadcast.status == BroadcastStatus.INTERRUPTED.value)
        )
        return [row[0] for row in ids_result.all()]

    async def get_resumable_broadcasts(self, max_age_hours: float) -> list[Broadcast]:
        """Прерванные рассылки, достаточно свежие для авто-возобновления."""
        if max_age_hours <= 0:
            return []
        cutoff = _utcnow() - timedelta(hours=max_age_hours)
        result = await self.session.execute(
            select(Broadcast).where(
                Broadcast.status == BroadcastStatus.INTERRUPTED.value,
                Broadcast.started_at >= cutoff,
            )
        )
        return list(result.scalars().all())

