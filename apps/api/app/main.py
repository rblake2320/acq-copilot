"""FastAPI application factory and configuration."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .config import settings
from .tools.registry import get_registry
from .tools import register_all_tools
from .services.cache import CacheService
from .routers import chat, tools, igce, regulatory, admin
from .routers import market_research
from .routers.rag import router as rag_router
from .models.database import Base

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global application state
db_engine = None
async_session_maker = None
cache_service = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler for startup and shutdown.

    Initializes:
    - Database engine and session factory
    - Redis cache service
    - Tool registry
    """
    global db_engine, async_session_maker, cache_service

    # Startup
    logger.info("app_startup", environment=settings.ENVIRONMENT)

    # Initialize database
    db_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.ENVIRONMENT == "dev",
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
    )
    async_session_maker = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    # Create tables
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns that may not exist in already-created tables (idempotent)
        await conn.execute(
            __import__("sqlalchemy").text(
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback INTEGER"
            )
        )
    logger.info("database_initialized")

    # Initialize cache service
    cache_service = CacheService(settings.REDIS_URL)
    try:
        await cache_service.connect()
        logger.info("cache_service_initialized")
    except Exception as e:
        logger.warning("cache_service_failed", error=str(e))
        cache_service = None

    # Initialize tool registry and register all tools
    registry = get_registry()
    tools_dict: dict = {}
    register_all_tools(tools_dict)
    for tool_id, tool_instance in tools_dict.items():
        registry.register(tool_instance)
    logger.info("tool_registry_initialized", tool_count=registry.count())

    yield

    # Shutdown
    logger.info("app_shutdown")
    if cache_service:
        await cache_service.close()
    if db_engine:
        await db_engine.dispose()
    if registry:
        await registry.close_all()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="AI-powered acquisition intelligence platform",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle uncaught exceptions."""
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_type": type(exc).__name__,
            },
        )

    # Health endpoint
    @app.get("/health")
    async def health_check() -> dict:
        """
        Basic health check endpoint.

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }

    # Include routers
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    app.include_router(igce.router, prefix="/api/igce", tags=["igce"])
    app.include_router(regulatory.router, prefix="/api/regulatory", tags=["regulatory"])
    app.include_router(market_research.router, prefix="/api/market-research", tags=["market-research"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    app.include_router(rag_router, prefix="/api/rag", tags=["rag"])

    # Root endpoint
    @app.get("/")
    async def root() -> dict:
        """Root endpoint."""
        return {
            "name": settings.APP_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
        }

    logger.info("app_created", version=settings.VERSION)
    return app


app = create_app()


# Dependency to get database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
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


# Dependency to get cache service
def get_cache() -> CacheService | None:
    """Get cache service."""
    return cache_service


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "dev",
        log_level=settings.LOG_LEVEL.lower(),
    )
