from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shopcrm_core.db.models.base import Base


class StockMovement(Base):
    """Журнал складских движений (append-only, неизменяемый).

    Каждое изменение балансов ``products`` (stock/reserved) фиксируется
    здесь в той же транзакции, что и само обновление балансов.
    ``quantity`` всегда положительное — направление движения задаёт
    ``type`` (см. ``StockMovementType``). Снимки ``stock_after`` /
    ``reserved_after`` позволяют сверить балансы по журналу.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
        Index("ix_stock_movements_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(20))  # значения StockMovementType
    quantity: Mapped[int] = mapped_column(Integer)
    stock_after: Mapped[int] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer)
    # Операции по заказам (reserved/released/sold)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    # Ручные операции администратора (arrived/written_off)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Комментарий администратора (причина/примечание к движению)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
