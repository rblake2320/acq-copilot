"""Shared FastAPI dependency functions (avoids circular imports with main.py)."""
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session — implementation injected at startup via main.py."""
    from .main import async_session_maker
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_cache():
    """Get cache service — implementation injected at startup via main.py."""
    from .main import cache_service
    return cache_service
