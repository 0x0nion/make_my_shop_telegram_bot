from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shopcrm_core.db.models.base import Base


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy для заданного DATABASE_URL.

    Фабрика: позволяет консьюмеру (self-hosted бот, хостинг-бот) создавать
    движок под свою БД без модульных синглтонов.
    """
    return create_async_engine(database_url, echo=echo)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику сессий для движка (``expire_on_commit=False``)."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Инициализация БД на старте.

    Всегда устанавливает соединение (fail-fast при недоступной БД).
    ``create_all`` выполняется только в режиме разработки (``echo=True``,
    т.е. ``DEBUG=True``): в продакшене схема управляется миграциями
    консьюмера (Alembic), метаданные для которых доступны через
    ``shopcrm_core.db.get_metadata()``.
    """
    async with engine.begin() as conn:
        if engine.echo:
            await conn.run_sync(Base.metadata.create_all)

