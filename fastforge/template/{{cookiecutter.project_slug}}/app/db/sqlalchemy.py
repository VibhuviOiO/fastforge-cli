"""SQLAlchemy async session factory — works with PostgreSQL, MySQL, and SQLite."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    """Dependency that provides an async database session."""
    async with async_session() as session:
        yield session
