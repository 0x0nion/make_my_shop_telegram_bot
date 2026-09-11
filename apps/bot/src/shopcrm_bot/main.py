import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.exc import OperationalError

from shopcrm_core.db.connection import (
    create_engine,
    create_session_factory,
    init_db,
)
from shopcrm_core.logging import setup_logging, shutdown_logging
from shopcrm_core.utils.retry import RetryConfig, retry_async

from shopcrm_bot.config import config
from shopcrm_bot.errors import register_error_handlers
from shopcrm_bot.handlers import routers as all_routers
from shopcrm_bot.middlewares.db import DbSessionMiddleware


def _create_storage() -> BaseStorage:
    """Создаёт хранилище FSM по конфигурации.

    - "memory" (по умолчанию): в памяти, для одного процесса.
    - "redis": в Redis, для персистентности и нескольких процессов.
    """
    if config.FSM_STORAGE.lower() == "redis":
        from aiogram.fsm.storage.redis import RedisStorage

        return RedisStorage.from_url(config.REDIS_URL)
    return MemoryStorage()


# Повторы инициализации БД при временных сбоях соединения (например, БД ещё
# поднимается в контейнеризованном окружении).
_DB_RETRY = RetryConfig(max_attempts=3, base_delay=1.0, max_delay=10.0)


async def _init_db_with_retry(engine: AsyncEngine) -> None:
    """Инициализация БД с повторами при временных ошибках соединения."""
    await retry_async(
        lambda: init_db(engine),
        config=_DB_RETRY,
        retry_on=(OperationalError, ConnectionError, TimeoutError),
        name="init_db",
    )


async def main():
    setup_logging(level=config.LOG_LEVEL, logs_dir=config.LOGS_DIR)

    engine = create_engine(config.DATABASE_URL, echo=config.DEBUG)
    session_factory = create_session_factory(engine)

    await _init_db_with_retry(engine)

    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=_create_storage())

    dp.update.middleware(DbSessionMiddleware(session_pool=session_factory))

    register_error_handlers(dp)

    dp.include_routers(all_routers)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        shutdown_logging()


if __name__ == "__main__":
    asyncio.run(main())
