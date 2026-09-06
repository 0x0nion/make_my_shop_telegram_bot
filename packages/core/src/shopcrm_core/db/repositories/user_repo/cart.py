from sqlalchemy import and_
from sqlalchemy.orm import selectinload, joinedload

from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.base_repo import BaseRepository
from shopcrm_core.logging import logger


class UserCartMixin:

    @property
    def _cart_repo(self) -> BaseRepository[CartItem]:
        return BaseRepository(CartItem, self.session)

    @property
    def _user_repo(self) -> BaseRepository[User]:
        return BaseRepository(User, self.session)

    async def add_to_cart(self, user_id: int, product_id: int) -> User | None:
        logger.info(f"Adding product id={product_id} to cart for user id={user_id}")
        cart_item = await self._cart_repo.get_one(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id
        )

        if cart_item:
            await self._cart_repo.update(cart_item.id, quantity=cart_item.quantity + 1)
        else:
            await self._cart_repo.create(user_id=user_id, product_id=product_id, quantity=1)

        # Сбрасываем кэш сессии, чтобы SQLAlchemy заново перечитала cart и product
        self.session.expire_all()

        return await self.get_cart_with_products(user_id)

    async def get_cart_with_products(self, user_id: int) -> User | None:
        options = [selectinload(User.cart).joinedload(CartItem.product)]
        return await self._user_repo.get_by_id(user_id, options=options)

    async def update_cart_item(self, user_id: int, product_id: int, change: int) -> User | None:
        logger.info(f"Updating cart item product_id={product_id} for user id={user_id} with change={change}")
        cart_item = await self._cart_repo.get_one(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id
        )

        if not cart_item:
            return await self.get_cart_with_products(user_id)

        new_quantity = cart_item.quantity + change
        if new_quantity <= 0:
            await self._cart_repo.delete_by_id(cart_item.id)
        else:
            await self._cart_repo.update(cart_item.id, quantity=new_quantity)

        # Сбрасываем кэш сессии, чтобы SQLAlchemy заново перечитала cart и product
        self.session.expire_all()

        return await self.get_cart_with_products(user_id)