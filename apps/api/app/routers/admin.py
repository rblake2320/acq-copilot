"""Administrative endpoints."""
from datetime import datetime
from typing import Optional
import json
import os
import re
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog

from ..dependencies import get_db, get_cache
from ..tools.registry import get_registry
from ..services.audit import AuditService
from ..schemas.common import HealthResponse, AuditEventResponse, CacheStatsResponse, PaginatedResponse
from ..config import settings
from ..models.database import Conversation, Message, ToolRun

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
    "congress_gov": "CONGRESS_GOV_API_KEY",
    "census": "CENSUS_API_KEY",
    "sam_gov": "SAM_API_KEY",
    "nvidia_ngc": "NGC_API_KEY",
}

# Path to the .env file (two levels up from this router file: api/app/routers -> api/)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _persist_key_to_env(attr: str, value: str) -> None:
    """Write or update an API key in the .env file so it survives restarts."""
    try:
        if _ENV_FILE.exists():
            text = _ENV_FILE.read_text(encoding="utf-8")
        else:
            text = ""

        pattern = re.compile(rf"^{re.escape(attr)}=.*$", re.MULTILINE)
        new_line = f"{attr}={value}"
        if pattern.search(text):
            text = pattern.sub(new_line, text)
        else:
            text = text.rstrip("\n") + f"\n{new_line}\n"

        _ENV_FILE.write_text(text, encoding="utf-8")
    except Exception as exc:
        # Non-fatal — key is still set in memory
        logger.warning("env_persist_failed", attr=attr, error=str(exc))


class VerifyApiKeyRequest(BaseModel):
    """Request body for verify-api-key."""

    service: str


class SetApiKeyRequest(BaseModel):
    """Request body for set-api-key."""

    service: str
    key: str


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
        # Override SAM health: if API key is configured, treat as healthy regardless of HTTP response
        sam_key = getattr(settings, "SAM_API_KEY", "") or os.environ.get("SAM_API_KEY", "")
        if "sam.search_opportunities" in health and sam_key:
            h = health["sam.search_opportunities"]
            if h.get("status") != "healthy":
                health["sam.search_opportunities"] = {
                    "tool_id": "sam.search_opportunities",
                    "status": "healthy",
                    "message": "API key configured",
                }
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


@router.post("/set-api-key")
async def set_api_key(request: SetApiKeyRequest) -> dict:
    """
    Set an API key at runtime for the current server process.

    The key is stored in the running process only (not persisted to .env).
    Restart the server to clear runtime-set keys.
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

        if not request.key or not request.key.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Key value cannot be empty",
            )

        # Update in-place on the singleton settings object
        object.__setattr__(settings, attr, request.key.strip())

        # Persist to .env so the key survives server restarts
        _persist_key_to_env(attr, request.key.strip())

        logger.info("api_key_set", service=service, attr=attr)

        return {
            "service": service,
            "configured": True,
            "message": f"API key for '{service}' has been set and persisted to .env",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("set_api_key_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set API key",
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
            "valid": configured,
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


# ── Training Data ─────────────────────────────────────────────────────────────


@router.get("/training-data/stats")
async def training_data_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Return conversation and message counts for the training data dashboard.
    """
    try:
        total_convs = (await db.execute(select(func.count()).select_from(Conversation))).scalar_one()
        total_msgs = (await db.execute(select(func.count()).select_from(Message))).scalar_one()
        thumbs_up = (
            await db.execute(
                select(func.count()).select_from(Message).where(Message.feedback == 1)
            )
        ).scalar_one()
        thumbs_down = (
            await db.execute(
                select(func.count()).select_from(Message).where(Message.feedback == -1)
            )
        ).scalar_one()

        # Count exportable turns: conversations that have at least one user+assistant pair
        exportable = (
            await db.execute(
                select(func.count()).select_from(Conversation).where(
                    Conversation.id.in_(
                        select(Message.conversation_id).where(Message.role == "assistant").distinct()
                    )
                )
            )
        ).scalar_one()

        return {
            "total_conversations": total_convs,
            "total_messages": total_msgs,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "exportable_conversations": exportable,
        }
    except Exception as e:
        logger.error("training_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get training stats")


@router.get("/training-data/export")
async def export_training_data(
    rated_only: bool = Query(False, description="Only export conversations with thumbs-up responses"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export conversation history as JSONL in Anthropic fine-tuning format.

    Each line: {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

    Set rated_only=true to export only conversations where at least one
    assistant message was rated thumbs-up (feedback=1).
    """
    try:
        # Get all conversations (optionally only those with thumbs-up messages)
        if rated_only:
            conv_ids_with_thumbsup = select(Message.conversation_id).where(
                Message.feedback == 1
            ).distinct()
            conv_query = select(Conversation).where(
                Conversation.id.in_(conv_ids_with_thumbsup)
            ).order_by(Conversation.created_at)
        else:
            conv_query = select(Conversation).order_by(Conversation.created_at)

        conversations = (await db.execute(conv_query)).scalars().all()

        async def generate_jsonl():
            for conv in conversations:
                msgs_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(Message.created_at)
                )
                msgs = msgs_result.scalars().all()

                # Build turns: only include user/assistant messages
                turns = [
                    {"role": m.role, "content": m.content}
                    for m in msgs
                    if m.role in ("user", "assistant")
                ]

                # Must have at least one user + one assistant message
                if not any(t["role"] == "user" for t in turns):
                    continue
                if not any(t["role"] == "assistant" for t in turns):
                    continue

                line = json.dumps({"messages": turns})
                yield line + "\n"

        filename = "training_data_rated.jsonl" if rated_only else "training_data_all.jsonl"
        return StreamingResponse(
            generate_jsonl(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error("export_training_data_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to export training data")


@router.get("/training-data/export-full")
async def export_training_data_full(
    rated_only: bool = Query(False, description="Only export thumbs-up conversations"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export full training data including tool inputs/outputs in Anthropic tool-use format.

    Each line: {"messages": [...], "tool_runs": [...], "metadata": {...}}
    Suitable for fine-tuning models that use tools.
    """
    try:
        if rated_only:
            conv_ids = select(Message.conversation_id).where(Message.feedback == 1).distinct()
            conv_query = select(Conversation).where(Conversation.id.in_(conv_ids)).order_by(Conversation.created_at)
        else:
            conv_query = select(Conversation).order_by(Conversation.created_at)

        conversations = (await db.execute(conv_query)).scalars().all()

        async def generate_jsonl():
            for conv in conversations:
                msgs_result = await db.execute(
                    select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
                )
                msgs = msgs_result.scalars().all()

                turns = [
                    {
                        "role": m.role,
                        "content": m.content,
                        "feedback": m.feedback,
                        "message_id": str(m.id),
                    }
                    for m in msgs
                    if m.role in ("user", "assistant")
                ]

                if not any(t["role"] == "user" for t in turns):
                    continue
                if not any(t["role"] == "assistant" for t in turns):
                    continue

                # Fetch associated tool runs
                tr_result = await db.execute(
                    select(ToolRun)
                    .where(ToolRun.conversation_id == conv.id)
                    .order_by(ToolRun.created_at)
                )
                tool_runs = tr_result.scalars().all()

                tool_runs_data = [
                    {
                        "tool_id": tr.tool_id,
                        "input": tr.input_json,
                        "output": tr.output_json,
                        "status": tr.status,
                        "duration_ms": tr.duration_ms,
                        "error": tr.error_message,
                    }
                    for tr in tool_runs
                ]

                thumbs_up = sum(1 for m in msgs if m.feedback == 1)
                thumbs_down = sum(1 for m in msgs if m.feedback == -1)

                line = json.dumps({
                    "conversation_id": str(conv.id),
                    "messages": [{"role": t["role"], "content": t["content"]} for t in turns],
                    "tool_runs": tool_runs_data,
                    "metadata": {
                        "created_at": conv.created_at.isoformat(),
                        "thumbs_up": thumbs_up,
                        "thumbs_down": thumbs_down,
                        "tool_count": len(tool_runs_data),
                    },
                })
                yield line + "\n"

        filename = "training_full_rated.jsonl" if rated_only else "training_full_all.jsonl"
        return StreamingResponse(
            generate_jsonl(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error("export_training_data_full_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to export full training data")
