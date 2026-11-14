# database/models/user.py
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.base import Base

if TYPE_CHECKING:
    from shopcrm_core.db.models.cart import CartItem
    from shopcrm_core.db.models.order import Order


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default='client')
    # Профиль клиента (из Telegram): имя и username для отчётов/карточек.
    # Заполняются при первом обращении и обновляются, если были пустыми.
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Персональная скидка клиента в процентах (0–100), устанавливается
    # администратором в карточке пользователя.
    # server_default — чтобы DDL из create_all совпадал с миграцией
    # (NUMERIC(5,2) NOT NULL DEFAULT 0) на всех схемах.
    discount: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.0, server_default=text("0"), nullable=False
    )

    # Добавляем lazy="selectin" для автоматической асинхронной подгрузки
    # order_by по id гарантирует стабильный порядок (порядок добавления),
    # чтобы при in-place редактировании сообщения кнопки не «перемешивались»
    cart: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        backref="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CartItem.id",
    )

    # foreign_keys: в orders два FK на users (user_id и paid_by) — указываем явно.
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Order.user_id",
    )

    @property
    def active_orders_count(self) -> int:
        """Количество заказов, кроме завершённых и отменённых."""
        return sum(1 for o in (self.orders or []) if not OrderStatus.is_final(o.status))