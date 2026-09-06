from typing import Optional
from sqlalchemy import ForeignKey, String, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.db.models.base import Base
from shopcrm_core.locales.units import DEFAULT_UNIT


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(20), default=DEFAULT_UNIT.value, nullable=False)
    image_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")