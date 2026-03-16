from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.database_url.replace("+aiosqlite", ""), echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine)


async def get_db():
    async with async_session_maker() as session:
        yield session
