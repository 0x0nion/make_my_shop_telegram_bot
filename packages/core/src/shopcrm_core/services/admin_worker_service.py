# src/services/admin_worker_service.py
"""Бизнес-логика управления работниками (админ-раздел «Работники»).

Список, добавление и удаление работников (администраторов).
Главный администратор из env — виртуальный: всегда присутствует в списке
и не может быть удалён (защита на уровне сервиса, не только UI).
"""
import logging
from dataclasses import dataclass

from shopcrm_core.db.models.worker import Worker
from shopcrm_core.db.repositories.admin_repo import AdminRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerEntry:
    """Строка списка работников (работник из БД или главный админ из env)."""

    telegram_id: int
    position: str
    is_main: bool = False


class AdminWorkerService:
    """Добавление/удаление работников и выдача доступа к админке."""

    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    async def list_workers(self, main_admin_ids: list[int]) -> list[WorkerEntry]:
        """Единый список: главный админ (env) + работники из БД."""
        entries = [
            WorkerEntry(telegram_id=tg_id, position="", is_main=True)
            for tg_id in main_admin_ids
        ]
        for worker in await self.admin_repo.get_workers():
            entries.append(
                WorkerEntry(telegram_id=worker.telegram_id, position=worker.position)
            )
        return entries

    async def add_worker(
        self,
        telegram_id: int,
        position: str,
        main_admin_ids: list[int],
    ) -> tuple[Worker | None, str | None]:
        """Добавление работника (после этого у него появляется доступ к админке).

        :return: ``(worker, None)`` при успехе или ``(None, error)``:
            ``"invalid_position"`` — должность пуста;
            ``"already_admin"`` — уже главный админ или уже работник.
        """
        position = (position or "").strip()
        if not position:
            return None, "invalid_position"
        if telegram_id in main_admin_ids or await self.admin_repo.get_worker_by_telegram_id(
            telegram_id
        ):
            return None, "already_admin"
        worker = await self.admin_repo.add_worker(telegram_id, position)
        logger.info(f"Worker added: telegram_id={telegram_id} position={position!r}")
        return worker, None

    async def remove_worker(
        self,
        telegram_id: int,
        main_admin_ids: list[int],
    ) -> tuple[bool, str | None]:
        """Удаление работника (снимает доступ к админке).

        :return: ``(True, None)`` при успехе или ``(False, error)``:
            ``"main_admin"`` — главного админа удалить нельзя;
            ``"not_found"`` — работника с таким ID нет.
        """
        if telegram_id in main_admin_ids:
            return False, "main_admin"
        removed = await self.admin_repo.remove_worker_by_telegram_id(telegram_id)
        if not removed:
            return False, "not_found"
        logger.info(f"Worker removed: telegram_id={telegram_id}")
        return True, None

    async def get_admin_ids(self, main_admin_ids: list[int]) -> list[int]:
        """Все ID администраторов: env + работники из БД (без дублей)."""
        worker_ids = await self.admin_repo.get_worker_telegram_ids()
        return list(dict.fromkeys([*main_admin_ids, *worker_ids]))
