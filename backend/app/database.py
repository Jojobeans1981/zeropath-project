from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


def get_async_url(url: str) -> str:
    """Convert DATABASE_URL to async driver format."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url  # sqlite+aiosqlite:// stays as-is


def get_sync_url(url: str) -> str:
    """Convert DATABASE_URL to sync driver format."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    # SQLite: strip aiosqlite
    return url.replace("+aiosqlite", "")


async_url = get_async_url(settings.database_url)
sync_url = get_sync_url(settings.database_url)

engine = create_async_engine(async_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(sync_url, echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine)


async def get_db():
    async with async_session_maker() as session:
        yield session
