from shopcrm_core.db.repositories.shop_repo.categories import ShopCategoriesMixin
from shopcrm_core.db.repositories.shop_repo.products import ShopProductsMixin


class ShopRepository(
    ShopCategoriesMixin,
    ShopProductsMixin
):
    """Репозиторий для работы исключительно с витриной магазина (клиентская часть)"""

    def __init__(self, session):
        self.session = session