import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from shopcrm_core.config import config
from shopcrm_core.db.connection import async_session, init_db

from shopcrm_bot.handlers import routers as all_routers
from shopcrm_bot.middlewares.db import DbSessionMiddleware
from aiogram.fsm.storage.memory import MemoryStorage


async def main():
    logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(
        storage=MemoryStorage()
    )

    dp.update.middleware(DbSessionMiddleware(session_pool=async_session))

    dp.include_routers(all_routers)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
