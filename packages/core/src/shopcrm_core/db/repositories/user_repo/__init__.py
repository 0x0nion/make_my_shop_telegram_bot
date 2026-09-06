from shopcrm_core.db.repositories.user_repo.account import UserAccountMixin
from shopcrm_core.db.repositories.user_repo.cart import UserCartMixin
from shopcrm_core.db.repositories.user_repo.locales import UserLocaleMixin
from shopcrm_core.db.repositories.user_repo.orders import UserOrderMixin


class UserRepository(
    UserAccountMixin,
    UserCartMixin,
    UserOrderMixin,
    UserLocaleMixin
):
    """Репозиторий для работы с аккаунтом пользователя, корзиной и заказами."""

    def __init__(self, session):
        self.session = session