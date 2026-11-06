# database/models/category.py
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.db.models.base import Base

if TYPE_CHECKING:
    from shopcrm_core.db.models.product import Product


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))

    # Новое поле флага активности
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    subcategories: Mapped[list["Category"]] = relationship("Category", back_populates="parent")
    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side=[id], back_populates="subcategories")

    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")