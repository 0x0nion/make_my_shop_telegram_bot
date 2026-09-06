# database/models/template.py
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from shopcrm_core.db.models.base import Base


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Имя шаблона, например 'product_view', 'cart_view'
    name: Mapped[str] = mapped_column(String(50), unique=True)
    # Сам шаблон с плейсхолдерами
    content: Mapped[str] = mapped_column(Text)