import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import config
from database.connection import async_session, init_db

from handlers import routers as all_routers
from middlewares.db import DbSessionMiddleware


async def main():
    logging.basicConfig(level=logging.INFO)

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
    