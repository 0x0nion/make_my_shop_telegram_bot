# database/models/category.py
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shopcrm_core.db.models.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))

    # Новое поле флага активности
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    subcategories: Mapped[List["Category"]] = relationship("Category", back_populates="parent")
    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side=[id], back_populates="subcategories")

    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")