"""Acquisition planning assistant endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from ..tools.threshold_checker import ThresholdCheckerTool
from ..tools.vehicle_recommender import VehicleRecommenderTool

router = APIRouter()
logger = structlog.get_logger(__name__)


class PlanningRequest(BaseModel):
    description: str
    estimated_value: Optional[int] = None
    naics_code: Optional[str] = None
    small_business_preference: bool = False
    agency_type: str = "civilian"  # "dod", "civilian"


class ThresholdRequest(BaseModel):
    contract_value: Optional[int] = None
    threshold_name: Optional[str] = None


@router.post("/strategy")
async def get_acquisition_strategy(request: PlanningRequest):
    """Get comprehensive acquisition strategy for a requirement."""
    try:
        import asyncio

        threshold_tool = ThresholdCheckerTool()
        vehicle_tool = VehicleRecommenderTool()

        threshold_task = threshold_tool.run({"contract_value": request.estimated_value})
        vehicle_task = vehicle_tool.run({
            "description": request.description,
            "naics_code": request.naics_code,
            "estimated_value": request.estimated_value or 0,
            "small_business": request.small_business_preference,
            "dod": request.agency_type == "dod",
        })

        threshold_result, vehicle_result = await asyncio.gather(threshold_task, vehicle_task)

        return {
            "requirement": request.description,
            "estimated_value": request.estimated_value,
            "thresholds": threshold_result.output,
            "vehicles": vehicle_result.output,
            "citations": [
                *[c.model_dump() for c in threshold_result.citations],
                *[c.model_dump() for c in vehicle_result.citations],
            ],
        }

    except Exception as e:
        logger.error("planning_strategy_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thresholds")
async def check_thresholds(request: ThresholdRequest):
    """Check applicable FAR thresholds for a contract value."""
    tool = ThresholdCheckerTool()
    result = await tool.run({
        "contract_value": request.contract_value,
        "threshold_name": request.threshold_name,
    })
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error_message)
    return result.output


@router.post("/vehicles")
async def recommend_vehicles(request: PlanningRequest):
    """Recommend contract vehicles for a requirement."""
    tool = VehicleRecommenderTool()
    result = await tool.run({
        "description": request.description,
        "naics_code": request.naics_code,
        "estimated_value": request.estimated_value or 0,
        "small_business": request.small_business_preference,
        "dod": request.agency_type == "dod",
    })
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error_message)
    return result.output
