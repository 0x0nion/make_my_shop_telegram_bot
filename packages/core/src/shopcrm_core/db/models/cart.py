# database/models/cart.py

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.db.models.base import Base

if TYPE_CHECKING:
    from shopcrm_core.db.models.product import Product


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(column="users.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey(column="products.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(default=1)
    product: Mapped["Product"] = relationship("Product", lazy="selectin")
