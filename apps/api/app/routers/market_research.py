"""Market research router — wraps USASpending and related tools."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import structlog

from ..tools.registry import get_registry

router = APIRouter()
logger = structlog.get_logger(__name__)


class USASpendingSearchRequest(BaseModel):
    """POST /usa-spending request body."""

    query: Optional[str] = Field(default=None, description="Search keywords")
    # Flat fields
    naics_codes: Optional[List[str]] = Field(default=None)
    psc_codes: Optional[List[str]] = Field(default=None)
    agency: Optional[str] = Field(default=None)
    date_range: Optional[dict] = Field(default=None)
    # Nested filters shape from frontend: {naicsCode, pscCode, agency}
    filters: Optional[dict] = Field(default=None)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)


@router.post("/usa-spending")
async def search_usa_spending(request: USASpendingSearchRequest) -> dict:
    """
    Search federal awards on USASpending.gov.

    Calls the usaspending.search_awards tool with action=search_awards,
    forwarding keywords, NAICS/PSC codes, agency, and date range filters.
    """
    try:
        registry = get_registry()
        tool = registry.get("usaspending.search_awards")

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="USASpending tool is not available",
            )

        # Merge flat fields and nested filters dict (frontend sends filters: {naicsCode, pscCode, agency})
        f = request.filters or {}
        naics = request.naics_codes or ([f["naicsCode"]] if f.get("naicsCode") else None)
        psc = request.psc_codes or ([f["pscCode"]] if f.get("pscCode") else None)
        agency = request.agency or f.get("agency")

        params: dict = {
            "action": "search_awards",
            "page": request.page,
            "limit": request.limit,
        }
        if request.query:
            params["keywords"] = request.query
        if naics:
            params["naics_codes"] = naics
        if psc:
            params["psc_codes"] = psc
        if agency:
            params["agency"] = agency
        if request.date_range:
            params["date_range"] = request.date_range

        result = await tool.execute(params)

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "USASpending search failed",
            )

        logger.info(
            "usa_spending_search_complete",
            query=request.query,
            status=result.status,
            duration_ms=result.duration_ms,
        )

        return {
            "status": result.status,
            "output": result.output,
            "duration_ms": result.duration_ms,
            "citations": [
                {
                    "source_name": c.source_name,
                    "source_url": c.source_url,
                    "source_label": c.source_label,
                    "retrieved_at": c.retrieved_at.isoformat(),
                }
                for c in result.citations
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("usa_spending_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search USASpending",
        )


@router.get("/trends/{naicsCode}")
async def market_trends_by_naics(
    naicsCode: str,
    agency: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """
    Get market trends for a given NAICS code by searching recent awards.
    """
    try:
        registry = get_registry()
        tool = registry.get("usaspending.search_awards")

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="USASpending tool is not available",
            )

        params: dict = {
            "action": "search_awards",
            "naics_codes": [naicsCode],
            "limit": limit,
        }
        if agency:
            params["agency"] = agency

        result = await tool.execute(params)

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "NAICS trends lookup failed",
            )

        output = result.output or {}
        awards = output.get("awards", [])

        # Compute a simple aggregated trend summary
        total_value = sum(a.get("award_amount", 0) for a in awards)
        agencies = list({a.get("agency_name", "") for a in awards if a.get("agency_name")})

        logger.info("market_trends_complete", naics=naicsCode, awards_count=len(awards))

        return {
            "naics_code": naicsCode,
            "total_awards": len(awards),
            "total_value": total_value,
            "top_agencies": agencies[:10],
            "awards": awards,
            "citations": [
                {
                    "source_name": c.source_name,
                    "source_url": c.source_url,
                    "source_label": c.source_label,
                    "retrieved_at": c.retrieved_at.isoformat(),
                }
                for c in result.citations
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("market_trends_failed", naics=naicsCode, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get market trends",
        )


@router.get("/competitive/{category}")
async def competitive_landscape(
    category: str,
    agency: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """
    Get competitive landscape for a service/product category by searching
    recent awards and summarising recipients.
    """
    try:
        registry = get_registry()
        tool = registry.get("usaspending.search_awards")

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="USASpending tool is not available",
            )

        params: dict = {
            "action": "search_awards",
            "keywords": category,
            "limit": limit,
        }
        if agency:
            params["agency"] = agency

        result = await tool.execute(params)

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "Competitive landscape lookup failed",
            )

        output = result.output or {}
        awards = output.get("awards", [])

        # Aggregate by recipient
        recipients: dict = {}
        for award in awards:
            name = award.get("recipient_name", "Unknown")
            if name not in recipients:
                recipients[name] = {"award_count": 0, "total_value": 0.0}
            recipients[name]["award_count"] += 1
            recipients[name]["total_value"] += award.get("award_amount", 0)

        sorted_recipients = sorted(
            [{"recipient": k, **v} for k, v in recipients.items()],
            key=lambda x: x["total_value"],
            reverse=True,
        )

        logger.info("competitive_landscape_complete", category=category, recipients=len(sorted_recipients))

        return {
            "category": category,
            "total_awards": len(awards),
            "competitors": sorted_recipients,
            "awards": awards,
            "citations": [
                {
                    "source_name": c.source_name,
                    "source_url": c.source_url,
                    "source_label": c.source_label,
                    "retrieved_at": c.retrieved_at.isoformat(),
                }
                for c in result.citations
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("competitive_landscape_failed", category=category, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitive landscape",
        )
