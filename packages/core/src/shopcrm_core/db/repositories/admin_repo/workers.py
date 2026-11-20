# database/repositories/admin_repo/workers.py
"""Репозиторий работников (админ-раздел «Работники»)."""
from sqlalchemy import select

from shopcrm_core.db.models.worker import Worker
from shopcrm_core.db.repositories.base_repo import BaseRepository


class AdminWorkersMixin:

    def _get_worker_repo(self) -> BaseRepository[Worker]:
        """Вспомогательный метод получения базового репозитория работников."""
        return BaseRepository(Worker, self.session)

    async def get_workers(self) -> list[Worker]:
        """Все работники.

        Сортировка по id asc — стабильный «порядок добавления»,
        чтобы при in-place редактировании сообщения кнопки не «перемешивались».
        """
        return await self._get_worker_repo().get_all(order_by=Worker.id.asc())

    async def get_worker_by_telegram_id(self, telegram_id: int) -> Worker | None:
        """Работник по Telegram ID."""
        return await self._get_worker_repo().get_one(Worker.telegram_id == telegram_id)

    async def add_worker(self, telegram_id: int, position: str) -> Worker:
        """Создание работника (telegram_id уникален — дубли отсечены сервисом)."""
        return await self._get_worker_repo().create(
            telegram_id=telegram_id, position=position
        )

    async def remove_worker_by_telegram_id(self, telegram_id: int) -> bool:
        """Удаление работника по Telegram ID. :return: True, если запись была."""
        return (
            await self._get_worker_repo().delete_where(Worker.telegram_id == telegram_id)
        ) > 0

    async def get_worker_telegram_ids(self) -> list[int]:
        """Telegram ID всех работников (для выдачи доступа к админке)."""
        result = await self.session.execute(select(Worker.telegram_id))
        return [row[0] for row in result.all()]
