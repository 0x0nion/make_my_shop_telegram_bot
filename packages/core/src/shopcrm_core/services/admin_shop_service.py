# src/services/admin_shop_service.py
from shopcrm_core.db.repositories.admin_repo import AdminRepository


class AdminShopService:
    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    async def start_editing_session(self, admin_id: int) -> None:
        """Инициализация временной сессии редактирования магазина."""
        await self.admin_repo.sync_to_temp(admin_id=admin_id)

    async def save_editing_session(self, admin_id: int) -> None:
        """Коммит изменений из временной сессии в основную базу."""
        await self.admin_repo.commit_changes(admin_id=admin_id)