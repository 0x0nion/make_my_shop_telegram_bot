# database/models/order.py
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(column="users.id", ondelete="CASCADE"))

    # Флаг оплаты и текстовый статус логистики
    is_paid: Mapped[bool] = mapped_column(default=False)  # <--- ДОБАВЛЯЕМ ФЛАГ
    status: Mapped[str] = mapped_column(String(50), default="pending")

    delivery_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

    total_price: Mapped[float] = mapped_column(Numeric(10, 2))

    # Поля подтверждения оплаты
    payment_proof_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_proof: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[int] = mapped_column()
    price_at_purchase: Mapped[float] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")