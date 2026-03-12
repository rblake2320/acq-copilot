"""SAM.gov opportunity search endpoints."""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import structlog

from ..tools.sam_opportunities import SamSearchTool

router = APIRouter()
logger = structlog.get_logger(__name__)


class OpportunitySearchRequest(BaseModel):
    query: str = ""
    naics_code: Optional[str] = None
    state: Optional[str] = None
    agency: Optional[str] = None
    set_aside: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=25)


@router.post("/search")
async def search_opportunities(request: OpportunitySearchRequest):
    """
    Search SAM.gov for active federal contract opportunities.

    Returns up to 25 opportunities matching the provided filters.
    Requires SAM_API_KEY environment variable (free key from api.data.gov).
    When no key is configured, returns an empty result with setup instructions.
    """
    try:
        tool = SamSearchTool()
        result = await tool.execute({
            "query": request.query,
            "naics_code": request.naics_code or "",
            "state": request.state or "",
            "agency": request.agency or "",
            "set_aside": request.set_aside or "",
            "limit": request.limit,
        })

        if result.status == "error" and result.output is None:
            raise HTTPException(status_code=500, detail=result.error_message or "SAM.gov tool error")

        api_key_configured = bool(
            result.output.get("api_key_configured") if isinstance(result.output, dict) else False
        )

        return {
            "data": result.output,
            "citations": [c.model_dump() for c in result.citations],
            "api_key_configured": api_key_configured,
            "sam_url": (
                f"https://sam.gov/search/?keywords={request.query}&index=opp"
                if request.query
                else "https://sam.gov/search/?index=opp"
            ),
            "duration_ms": result.duration_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("opportunities_search_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/set-asides")
async def list_set_asides():
    """
    List SAM.gov set-aside type codes and labels.

    Use these codes in the `set_aside` field of /search requests.
    """
    return {
        "set_asides": [
            {"code": "SBA", "label": "Small Business"},
            {"code": "8A", "label": "8(a) Business Development"},
            {"code": "HZC", "label": "HUBZone Small Business"},
            {"code": "SDVOSBC", "label": "Service-Disabled Veteran-Owned Small Business"},
            {"code": "WOSB", "label": "Women-Owned Small Business"},
            {"code": "EDWOSB", "label": "Economically Disadvantaged WOSB"},
            {"code": "IEE", "label": "Indian Economic Enterprise"},
            {"code": "ISBEE", "label": "Indian Small Business Economic Enterprise"},
        ]
    }


@router.get("/health")
async def opportunities_health():
    """Check SAM.gov tool health and API key status."""
    tool = SamSearchTool()
    health = await tool.healthcheck()
    api_key_present = bool(
        os.environ.get("SAM_API_KEY")
        or getattr(__import__("app.config", fromlist=["settings"]).settings, "SAM_API_KEY", None)
    )
    return {
        **health,
        "api_key_configured": api_key_present,
        "get_key_url": "https://api.data.gov/signup/",
    }
