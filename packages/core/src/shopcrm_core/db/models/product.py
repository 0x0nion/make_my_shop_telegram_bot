from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.db.models.base import Base
from shopcrm_core.locales.units import DEFAULT_UNIT

if TYPE_CHECKING:
    from shopcrm_core.db.models.category import Category


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(28, 18))
    unit: Mapped[str] = mapped_column(String(20), default=DEFAULT_UNIT.value, nullable=False)
    image_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    # Остаток на складе. Видимость для клиента = is_active AND (stock - reserved) > 0
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Заморожено активными заказами (бронирование). Доступно клиенту = stock - reserved
    reserved: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Накопительные метрики склада (для отчётности)
    total_sold: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    total_arrived: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    total_written_off: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")