# database/models/setting.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shopcrm_core.db.models.base import Base


class Setting(Base):
    """Ключ-значение для настроек магазина (базовая инфраструктура).

    Одна строка на ``key``. Значение хранится как текст — интерпретация
    (число/флаг/строка) — за сервисом-потребителем. ``updated_by`` хранит
    Telegram ID администратора, который последний раз менял значение.
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
