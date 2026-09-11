import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Импортируем ваш экземпляр конфигурации и базовый класс моделей
from shopcrm_core.config import get_config
# Импортируем все модели из пакета database.models (благодаря __init__.py они зарегистрируются в Base.metadata)
from shopcrm_core.db.models import Base  # noqa: F401

# Это объект конфигурации Alembic (берет значения из alembic.ini)
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Указываем метаданные всех ваших моделей
target_metadata = Base.metadata

# Берём URL базы данных прямо из вашего pydantic-конфига
db_url = get_config().DATABASE_URL


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме (без создания Engine)."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Создание асинхронного подключения и выполнение миграций."""
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = db_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()