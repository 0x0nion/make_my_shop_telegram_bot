"""Публичный API слоя данных SHOPCRM core.

Core — библиотека: миграции (Alembic) и управление схемой принадлежат
консьюмерам (бот, админ-панель и т.д.). Чтобы консьюмер мог построить
`Base.metadata` для генерации/проверки миграций, здесь:

- импортируются все модели (чтобы `Base.metadata` был заполнен);
- экспортируется `Base`;
- предоставляется `get_metadata()` — единая точка доступа к метаданным.
"""
from shopcrm_core.db.models.base import Base

# Импорт моделей регистрирует все таблицы в Base.metadata.
from shopcrm_core.db.models import (  # noqa: F401
    CartItem,
    Category,
    LocaleText,
    Order,
    OrderItem,
    Product,
    TempCategory,
    TempLocaleText,
    TempProduct,
    Template,
    User,
)

__all__ = ["Base", "get_metadata"]


def get_metadata():
    """Возвращает `MetaData` SQLAlchemy со всеми таблицами core.

    Гарантирует, что все модели импортированы (таблицы зарегистрированы),
    и отдаёт `Base.metadata` для использования в Alembic/миграциях консьюмера.
    """
    return Base.metadata

