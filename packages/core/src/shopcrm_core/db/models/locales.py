# database/models/locales.py
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shopcrm_core.db.models.base import Base


class LocaleText(Base):
    __tablename__ = "locale_texts"

    id: Mapped[int] = mapped_column(primary_key=True)

    entity_type: Mapped[str] = mapped_column(String(50), index=True)

    entity_id: Mapped[int] = mapped_column(index=True, default=0)

    language_code: Mapped[str] = mapped_column(String(10), index=True)

    text: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "language_code",
            name="uq_entity_lang"
        ),
    )