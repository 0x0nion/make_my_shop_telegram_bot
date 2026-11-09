from shopcrm_core.db.repositories.admin_repo.categories import AdminCategoriesMixin
from shopcrm_core.db.repositories.admin_repo.locales import AdminLocalesMixin
from shopcrm_core.db.repositories.admin_repo.orders import AdminOrdersMixin
from shopcrm_core.db.repositories.admin_repo.products import AdminProductsMixin
from shopcrm_core.db.repositories.admin_repo.settings import AdminSettingsMixin
from shopcrm_core.db.repositories.admin_repo.sync import AdminSyncMixin
from shopcrm_core.db.repositories.order_audit import OrderAuditMixin


class AdminRepository(
    AdminCategoriesMixin,
    AdminProductsMixin,
    AdminLocalesMixin,
    AdminSyncMixin,
    AdminOrdersMixin,
    AdminSettingsMixin,
    OrderAuditMixin
):
    SUPPORTED_LANGUAGES = ["ru", "en", "es"]

    def __init__(self, session):
        self.session = session