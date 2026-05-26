"""
Async SQLAlchemy engine + session.
Работает и с SQLite (локально), и с PostgreSQL (продакшен).
"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from core.config import settings

_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_tables():
    """Создать все таблицы (checkfirst=True — не падает если уже есть)."""
    from core.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)


async def get_session():
    """Dependency для FastAPI."""
    async with async_session() as session:
        yield session
