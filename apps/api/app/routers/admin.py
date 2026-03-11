"""Administrative endpoints."""
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import structlog

from ..dependencies import get_db, get_cache
from ..tools.registry import get_registry
from ..services.audit import AuditService
from ..schemas.common import HealthResponse, AuditEventResponse, CacheStatsResponse, PaginatedResponse
from ..config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

# Mapping of service names to the Settings attribute that holds their API key
_SERVICE_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "bls": "BLS_API_KEY",
    "gsa_perdiem": "GSA_PERDIEM_API_KEY",
    "regulations_gov": "REGULATIONS_GOV_API_KEY",
}


class VerifyApiKeyRequest(BaseModel):
    """Request body for verify-api-key."""

    service: str


@router.get("/health", response_model=HealthResponse)
async def system_health(
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
) -> HealthResponse:
    """
    Check overall system health.

    Args:
        db: Database session
        cache: Cache service

    Returns:
        System health status
    """
    try:
        services = {}

        # Database
        try:
            await db.execute("SELECT 1")
            services["database"] = "healthy"
        except Exception as e:
            logger.warning("database_health_check_failed", error=str(e))
            services["database"] = "unhealthy"

        # Cache
        if cache:
            try:
                health = await cache.redis.ping() if cache.redis else False
                services["cache"] = "healthy" if health else "unhealthy"
            except Exception as e:
                logger.warning("cache_health_check_failed", error=str(e))
                services["cache"] = "unhealthy"
        else:
            services["cache"] = "unavailable"

        # Determine overall status
        status_value = "healthy"
        if "unhealthy" in services.values():
            status_value = "degraded"
        if all(v == "unhealthy" for v in services.values()):
            status_value = "unhealthy"

        return HealthResponse(
            status=status_value,
            timestamp=datetime.utcnow(),
            version="0.1.0",
            services=services,
        )
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check health",
        )


@router.get("/tools/status")
async def tools_status() -> dict:
    """
    Get status of all tools.

    Returns:
        Tools health status
    """
    try:
        registry = get_registry()
        health = await registry.health_check_all()
        return {
            "total_tools": registry.count(),
            "health_checks": health,
        }
    except Exception as e:
        logger.error("tools_status_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tools status",
        )


@router.get("/audit", response_model=PaginatedResponse[AuditEventResponse])
async def get_audit_log(
    event_type: str = None,
    entity_type: str = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuditEventResponse]:
    """
    Get paginated audit log.

    Args:
        event_type: Filter by event type
        entity_type: Filter by entity type
        skip: Pagination offset
        limit: Results per page
        db: Database session

    Returns:
        Paginated audit events
    """
    try:
        audit_service = AuditService()
        events, total = await audit_service.query_events(
            db=db,
            event_type=event_type,
            entity_type=entity_type,
            limit=limit,
            offset=skip,
        )

        items = [
            AuditEventResponse(
                id=e.id,
                actor_id=e.actor_id,
                event_type=e.event_type,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                details=e.details_json,
                created_at=e.created_at,
            )
            for e in events
        ]

        pages = (total + limit - 1) // limit
        return PaginatedResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            pages=pages,
        )
    except Exception as e:
        logger.error("audit_log_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get audit log",
        )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def cache_stats(
    cache=Depends(get_cache),
) -> CacheStatsResponse:
    """
    Get cache statistics.

    Args:
        cache: Cache service

    Returns:
        Cache statistics
    """
    try:
        if cache:
            stats = await cache.get_stats()
            return CacheStatsResponse(**stats)
        else:
            return CacheStatsResponse(
                hit_rate=0.0,
                total_hits=0,
                total_misses=0,
                keys_count=0,
                memory_bytes=0,
            )
    except Exception as e:
        logger.error("cache_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache stats",
        )


@router.post("/cache/clear")
async def cache_clear(
    cache=Depends(get_cache),
) -> dict:
    """
    Clear all entries from the cache.

    Returns:
        Success status and whether the cache was actually cleared
    """
    try:
        if cache:
            cleared = await cache.clear_all()
            logger.info("cache_cleared_via_api", cleared=cleared)
            return {"status": "success", "cleared": cleared, "message": "Cache cleared"}
        else:
            return {"status": "skipped", "cleared": False, "message": "Cache service not available"}
    except Exception as e:
        logger.error("cache_clear_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache",
        )


@router.get("/api-keys")
async def list_api_keys() -> dict:
    """
    List which API keys are configured (present/absent — values are never returned).

    Returns:
        Dict mapping service name to whether a key is configured
    """
    try:
        key_status = {}
        for service, attr in _SERVICE_KEY_MAP.items():
            value = getattr(settings, attr, None)
            key_status[service] = {
                "configured": bool(value),
                "attribute": attr,
            }
        return {"api_keys": key_status}
    except Exception as e:
        logger.error("list_api_keys_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API key configuration",
        )


@router.post("/verify-api-key")
async def verify_api_key(request: VerifyApiKeyRequest) -> dict:
    """
    Check whether an API key for a given service is configured.

    The key value is never returned — only whether it is present.

    Args:
        request: Service name to check

    Returns:
        configured: True if key is set, False otherwise
    """
    try:
        service = request.service.lower()
        attr = _SERVICE_KEY_MAP.get(service)

        if attr is None:
            available = list(_SERVICE_KEY_MAP.keys())
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown service '{service}'. Available: {available}",
            )

        value = getattr(settings, attr, None)
        configured = bool(value)

        logger.info("api_key_verified", service=service, configured=configured)

        return {
            "service": service,
            "configured": configured,
            "message": f"API key for '{service}' is {'configured' if configured else 'not configured'}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_api_key_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify API key",
        )
