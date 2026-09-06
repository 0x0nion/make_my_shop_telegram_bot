# database/models/user.py
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models.base import Base
from src.core.constants import OrderStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default='client')

    # Добавляем lazy="selectin" для автоматической асинхронной подгрузки
    cart: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        backref="user",
        cascade="all, delete-orphan",
        lazy="selectin"  # <--- Добавь этот параметр
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    @property
    def active_orders_count(self) -> int:
        """Количество заказов, кроме завершённых и отменённых."""
        return sum(1 for o in (self.orders or []) if not OrderStatus.is_final(o.status))