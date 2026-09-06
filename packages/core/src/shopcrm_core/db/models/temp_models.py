from typing import Optional
from sqlalchemy import String, Text, Numeric, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shopcrm_core.db.models.base import Base
from shopcrm_core.locales.units import DEFAULT_UNIT


class TempCategory(Base):
    __tablename__ = "temp_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger)


class TempProduct(Base):
    __tablename__ = "temp_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(20), default=DEFAULT_UNIT.value, nullable=False)
    image_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)


class TempLocaleText(Base):
    __tablename__ = "temp_locale_texts"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    language_code: Mapped[str] = mapped_column(String(10), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    __table_args__ = (
        UniqueConstraint(
            "entity_id", "entity_type", "language_code", "admin_id",
            name="uq_temp_locale"
        ),
    )