from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.infra.settings import get_settings


class Base(DeclarativeBase):
    """Base declarative model class."""


settings = get_settings()
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    # Managed PostgreSQL providers may retire idle TLS connections. Validate a pooled
    # connection before checkout and recycle it periodically instead of surfacing a
    # stale-connection 500 to the first request after an idle period.
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_db_session_context() -> AsyncIterator[AsyncSession]:
    """Context manager version of get_db_session for use in lifespan events."""
    async with SessionLocal() as session:
        yield session
