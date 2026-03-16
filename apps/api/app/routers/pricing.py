"""Price reasonableness analysis endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from ..tools.price_reasonableness import PriceReasonablenessTool

router = APIRouter()
logger = structlog.get_logger(__name__)


class PriceAnalysisRequest(BaseModel):
    occupation: str
    soc_code: Optional[str] = None
    location: Optional[str] = None
    proposed_rate: Optional[float] = None
    experience_level: str = "mid"


@router.post("/analyze")
async def analyze_price(request: PriceAnalysisRequest):
    """Analyze price reasonableness for a labor category."""
    try:
        tool = PriceReasonablenessTool()
        result = await tool.run({
            "occupation": request.occupation,
            "soc_code": request.soc_code,
            "location": request.location,
            "proposed_rate": request.proposed_rate,
            "experience_level": request.experience_level,
        })

        if result.status == "error" and not result.output:
            raise HTTPException(status_code=500, detail=result.error_message)

        return {
            "analysis": result.output,
            "citations": [c.model_dump() for c in result.citations],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pricing_analysis_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
