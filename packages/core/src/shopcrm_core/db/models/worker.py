# database/models/worker.py
"""Модель работника (администратора, добавленного через админ-панель).

Главный администратор из env (``ADMIN_ID``) в этой таблице НЕ хранится —
он виртуальный: всегда имеет доступ и его нельзя удалить.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shopcrm_core.db.models.base import Base


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Telegram ID работника — уникальный, по нему выдаётся доступ к админке.
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    # Должность (свободный текст: «Менеджер», «Курьер» и т.д.).
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
