"""Общие фикстуры для тестов SHOPCRM core."""
import os

# Устанавливаем тестовые env ДО импорта shopcrm_core.config
os.environ.setdefault("BOT_TOKEN", "123:TEST")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ADMIN_ID", "[1]")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shopcrm_core.db.models.base import Base
from shopcrm_core.db.models.user import User
from shopcrm_core.db.models.product import Product
from shopcrm_core.db.models.cart import CartItem
from shopcrm_core.db.models.order import Order, OrderItem
from shopcrm_core.db.repositories.user_repo import UserRepository


@pytest_asyncio.fixture
async def engine():
    """In-memory SQLite engine на каждый тест."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """AsyncSession, привязанная к in-memory БД."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def repo(session) -> UserRepository:
    """UserRepository с тестовой сессией."""
    return UserRepository(session)


# --- Seed-фикстуры ---

@pytest_asyncio.fixture
async def user_a(session) -> User:
    """Пользователь A (id=100)."""
    u = User(id=100, language="ru")
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def user_b(session) -> User:
    """Пользователь B (id=200)."""
    u = User(id=200, language="en")
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def product_a(session) -> Product:
    """Товар A: цена 10.00, 1 шт."""
    p = Product(name="Widget", price=10.00, unit="pc")
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
async def product_b(session) -> Product:
    """Товар B: цена 25.50, 1 шт."""
    p = Product(name="Gadget", price=25.50, unit="kg")
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
async def cart_with_items(session, user_a, product_a, product_b) -> None:
    """Корзина user_a: 2×Widget + 1×Gadget."""
    items = [
        CartItem(user_id=user_a.id, product_id=product_a.id, quantity=2),
        CartItem(user_id=user_a.id, product_id=product_b.id, quantity=1),
    ]
    session.add_all(items)
    await session.commit()
