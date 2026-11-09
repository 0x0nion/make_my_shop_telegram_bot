from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.db.models.base import Base

if TYPE_CHECKING:
    from shopcrm_core.db.models.product import Product
    from shopcrm_core.db.models.user import User


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(column="users.id", ondelete="CASCADE"))

    # Флаг оплаты и текстовый статус логистики
    is_paid: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")

    delivery_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_address_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "location" | "text"
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_price: Mapped[float] = mapped_column(Numeric(28, 18), default=0.0)

    total_price: Mapped[float] = mapped_column(Numeric(28, 18))

    # Поля подтверждения оплаты
    payment_proof_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_proof: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Хранение истории переписки по заказу (список словарей с отправителем, текстом и временем)
    chat_history: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Аудит: когда заказ последний раз изменялся и когда достиг финальных статусов
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Аудит оплаты: когда и кем (админ/клиент) отмечен как оплаченный
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # foreign_keys: в orders два FK на users (user_id и paid_by) — указываем явно,
    # чтобы SQLAlchemy не путал пути при настройке relationship.
    user: Mapped["User"] = relationship("User", back_populates="orders", foreign_keys=[user_id])
    # order_by по id гарантирует стабильный порядок позиций (порядок добавления),
    # чтобы при in-place редактировании сообщения кнопки не «перемешивались»
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderItem.id",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[int] = mapped_column()
    price_at_purchase: Mapped[float] = mapped_column(Numeric(28, 18))

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", lazy="selectin")


class OrderStatusHistory(Base):
    """Журнал смены статусов заказа (append-only, неизменяемый).

    Каждая смена ``Order.status`` фиксируется здесь: кто (``changed_by``)
    и когда перевёл заказ из ``old_status`` в ``new_status``. Строки не
    обновляются и не удаляются при жизни заказа; старые записи очищаются
    по политике хранения (см. ``RetentionService``).
    """

    __tablename__ = "order_status_history"
    __table_args__ = (
        Index("ix_order_status_history_order_created", "order_id", "created_at"),
        # Отдельный индекс по created_at — для периодической очистки по возрасту
        # (RetentionService): DELETE ... WHERE created_at < cutoff.
        Index("ix_order_status_history_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50))
    # Кто изменил статус: Telegram ID администратора или клиента
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())