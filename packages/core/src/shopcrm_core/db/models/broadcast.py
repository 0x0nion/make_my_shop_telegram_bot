# db/models/broadcast.py
"""Модели рассылки (broadcast).

БД — единственный источник истины: рассылка переживает рестарт бота,
повторные отправки исключены (UNIQUE по паре broadcast_id + user_id),
неактивным пользователям (заблокировали бота) не отправляется ничего.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopcrm_core.db.models.base import Base


class BroadcastStatus(str, Enum):  # noqa: UP042  # str-Enum: str() даёт value; StrEnum меняет поведение str()/format
    """Жизненный цикл рассылки."""

    PENDING = "pending"          # Создана, ожидает запуска
    RUNNING = "running"          # Отправляется
    CANCELLING = "cancelling"    # Админ запросил остановку (отправляется текущий чанк)
    COMPLETED = "completed"      # Завершена
    CANCELLED = "cancelled"      # Остановлена админом
    INTERRUPTED = "interrupted"  # Прервана рестартом бота (можно возобновить)


class RecipientStatus(str, Enum):  # noqa: UP042  # str-Enum: str() даёт value; StrEnum меняет поведение str()/format
    """Статус получателя внутри рассылки."""

    PENDING = "pending"          # Ожидает отправки
    SENT = "sent"                # Доставлено
    FAILED = "failed"            # Ошибки исчерпаны (сеть и т.п.)
    BLOCKED = "blocked"          # Пользователь заблокировал бота (повторов не будет)
    SKIPPED = "skipped"          # Пропущен (например, cooldown)
    RETRY_ASYNC = "retry_async"  # Временный сбой, будет повтор


class Broadcast(Base):
    """Рассылка: текст + снапшот получателей + счётчики."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=BroadcastStatus.PENDING.value, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recipients: Mapped[list["BroadcastRecipient"]] = relationship(
        back_populates="broadcast", cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        """Идёт ли рассылка (или готовится к остановке)."""
        return self.status in (
            BroadcastStatus.PENDING.value,
            BroadcastStatus.RUNNING.value,
            BroadcastStatus.CANCELLING.value,
        )

    @property
    def is_final(self) -> bool:
        return self.status in (
            BroadcastStatus.COMPLETED.value,
            BroadcastStatus.CANCELLED.value,
        )


class BroadcastRecipient(Base):
    """Получатель рассылки (строка снапшота)."""

    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipients"),
        # Частый запрос: pending-получатели рассылки (чанки отправки).
        Index("ix_broadcast_recipients_status", "broadcast_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default=RecipientStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    broadcast: Mapped["Broadcast"] = relationship(back_populates="recipients")
