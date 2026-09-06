from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from shopcrm_core.config import config
from shopcrm_core.db.models.base import Base

engine = create_async_engine(config.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

