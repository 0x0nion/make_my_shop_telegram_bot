# src/services/broadcast_service.py
"""Бизнес-логика рассылки (broadcast).

Отвечает за:
  - создание рассылки со снапшотом получателей (cooldown против спама,
    исключение админов и заблокировавших бота);
  - отмену (до запуска — удаление, во время — graceful-остановка);
  - выдачу результата последней рассылки для UI.

Отправку сообщений выполняет консьюмер (бот) — ``BroadcastSender``:
core не знает про Telegram API.
"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from shopcrm_core.db.models.broadcast import Broadcast, BroadcastStatus
from shopcrm_core.db.repositories.admin_repo import AdminRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadcastCreateResult:
    """Результат создания рассылки.

    :param broadcast: созданная рассылка (``None`` при ошибке);
    :param error: код ошибки (``None`` при успехе):
        ``"empty_text"`` — текст пуст;
        ``"already_active"`` — у админа уже идёт рассылка;
        ``"no_recipients"`` — получателей нет (cooldown/заблокированы/админы);
    :param recipients: сколько получателей в снапшоте;
    :param skipped: сколько пользователей исключено (cooldown/блокировки/админы).
    """

    broadcast: Broadcast | None
    error: str | None
    recipients: int = 0
    skipped: int = 0


class BroadcastService:
    """Создание/отмена рассылки и выдача результата последней."""

    def __init__(self, admin_repo: AdminRepository, cooldown_hours: float = 24.0):
        self.admin_repo = admin_repo
        self.cooldown_hours = cooldown_hours

    async def create(
        self,
        admin_id: int,
        text: str,
        admin_ids: list[int],
    ) -> BroadcastCreateResult:
        """Создать рассылку со снапшотом получателей.

        Cooldown: пользователи, которым уже отправляли в последние
        ``cooldown_hours`` часов, в снапшот не попадают (анти-спам).
        """
        text = (text or "").strip()
        if not text:
            return BroadcastCreateResult(None, "empty_text")

        if await self.admin_repo.get_active_broadcast(admin_id):
            return BroadcastCreateResult(None, "already_active")

        cooldown_since: datetime | None = None
        if self.cooldown_hours > 0:
            cooldown_since = datetime.now(UTC) - timedelta(hours=self.cooldown_hours)

        user_ids = await self.admin_repo.snapshot_recipients(admin_ids, cooldown_since)
        if not user_ids:
            return BroadcastCreateResult(None, "no_recipients")

        total_users = await self.admin_repo.count_active_users()
        skipped = max(0, total_users - len(user_ids))

        broadcast = await self.admin_repo.create_broadcast(
            admin_id=admin_id, text=text, total=len(user_ids), skipped=skipped
        )
        await self.admin_repo.create_recipients(broadcast.id, user_ids)
        logger.info(
            f"Broadcast created: id={broadcast.id} admin={admin_id} "
            f"recipients={len(user_ids)} skipped={skipped}"
        )
        return BroadcastCreateResult(broadcast, None, len(user_ids), skipped)

    async def cancel(self, admin_id: int, broadcast_id: int) -> str:
        """Отменить рассылку.

        :return: ``"cancelled"`` — остановка запрошена (или уже завершена),
            ``"not_found"`` — рассылка не найдена или не принадлежит админу.
        """
        broadcast = await self.admin_repo.get_broadcast(broadcast_id)
        if not broadcast or broadcast.admin_id != admin_id:
            return "not_found"
        if broadcast.status in (BroadcastStatus.PENDING.value, BroadcastStatus.RUNNING.value):
            await self.admin_repo.request_cancel(broadcast_id)
            logger.info(f"Broadcast cancel requested: id={broadcast_id} admin={admin_id}")
            return "cancelled"
        # Уже завершена/останавливается — делать нечего
        return "cancelled"

    async def delete_pending(self, admin_id: int, broadcast_id: int) -> bool:
        """Удалить рассылку до запуска (отмена на экране подтверждения)."""
        broadcast = await self.admin_repo.get_broadcast(broadcast_id)
        if not broadcast or broadcast.admin_id != admin_id:
            return False
        if broadcast.status != BroadcastStatus.PENDING.value:
            return False
        await self.admin_repo.delete_broadcast(broadcast_id)
        logger.info(f"Broadcast deleted before start: id={broadcast_id} admin={admin_id}")
        return True

    async def get_last_result(self, admin_id: int) -> Broadcast | None:
        """Последняя рассылка админа (для экрана «результат»)."""
        return await self.admin_repo.get_latest_broadcast(admin_id)
