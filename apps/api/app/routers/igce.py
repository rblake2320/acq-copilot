"""IGCE (Independent Government Cost Estimate) router."""
from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import uuid
import structlog

from ..dependencies import get_db
from ..models.database import IGCEProject
from ..schemas.common import PaginatedResponse
from ..tools.registry import get_registry

router = APIRouter()
logger = structlog.get_logger(__name__)


class LaborCategory(BaseModel):
    """Labor category for IGCE calculation."""

    title: str
    soc_code: str
    fte_count: float
    location_code: str = "US000000"


class IGCECalculateRequest(BaseModel):
    """Request body for IGCE calculate/build endpoints."""

    labor_categories: List[LaborCategory]
    base_year: int
    option_years: int = Field(default=1, ge=0)
    burden_multiplier: float = Field(default=2.0, ge=1.0)
    escalation_rate: float = Field(default=0.03, ge=0.0)
    productive_hours: int = Field(default=1880, ge=1)
    escalation_method: str = Field(default="compound", pattern="^(compound|simple)$")
    scenario: str = Field(default="base", pattern="^(base|low|high)$")
    include_validation: bool = False


@router.post("/calculate")
async def calculate_igce(request: IGCECalculateRequest) -> dict:
    """
    Build a comprehensive IGCE using the igce.build tool.

    Accepts labor categories, base year, option years, burden multiplier,
    and escalation rate and returns a full cost estimate.
    """
    try:
        registry = get_registry()
        tool = registry.get("igce.build")
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="IGCE build tool is not available",
            )

        params = {
            "action": "build",
            "labor_categories": [lc.model_dump() for lc in request.labor_categories],
            "base_year": request.base_year,
            "option_years": request.option_years,
            "burden_multiplier": request.burden_multiplier,
            "escalation_rate": request.escalation_rate,
            "productive_hours": request.productive_hours,
            "escalation_method": request.escalation_method,
            "scenario": request.scenario,
            "include_validation": request.include_validation,
        }

        result = await tool.execute(params)

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "IGCE calculation failed",
            )

        logger.info("igce_calculated", grand_total=result.output.get("grand_total") if result.output else None)

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
        logger.error("igce_calculate_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate IGCE",
        )


@router.post("/build")
async def build_igce(request: IGCECalculateRequest) -> dict:
    """
    Alias for POST /igce/calculate — build a comprehensive IGCE.
    """
    return await calculate_igce(request)


class IGCEEstimateRequest(BaseModel):
    """IGCE estimate request."""

    scope: str
    labor_hours: float
    labor_rate: float
    materials_cost: float
    overhead_percentage: float
    profit_margin_percentage: float


class IGCEEstimateResponse(BaseModel):
    """IGCE estimate response."""

    total_labor: float
    total_materials: float
    subtotal: float
    overhead: float
    profit: float
    total_estimate: float


class IGCEProjectCreate(BaseModel):
    """Create IGCE project request."""

    title: str
    assumptions: dict


class IGCEProjectResponse(BaseModel):
    """IGCE project response."""

    id: uuid.UUID
    title: str
    assumptions: dict
    result: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


@router.post("/estimate", response_model=IGCEEstimateResponse)
async def estimate_igce(request: IGCEEstimateRequest) -> IGCEEstimateResponse:
    """
    Run IGCE computation.

    Args:
        request: IGCE estimate parameters

    Returns:
        Cost estimate
    """
    try:
        # Calculate costs
        total_labor = request.labor_hours * request.labor_rate
        total_materials = request.materials_cost
        subtotal = total_labor + total_materials

        overhead = subtotal * (request.overhead_percentage / 100)
        adjusted_subtotal = subtotal + overhead

        profit = adjusted_subtotal * (request.profit_margin_percentage / 100)
        total_estimate = adjusted_subtotal + profit

        logger.info(
            "igce_estimate_calculated",
            scope=request.scope,
            total_estimate=total_estimate,
        )

        return IGCEEstimateResponse(
            total_labor=round(total_labor, 2),
            total_materials=round(total_materials, 2),
            subtotal=round(subtotal, 2),
            overhead=round(overhead, 2),
            profit=round(profit, 2),
            total_estimate=round(total_estimate, 2),
        )
    except Exception as e:
        logger.error("igce_estimate_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate estimate",
        )


@router.get("/projects", response_model=PaginatedResponse[IGCEProjectResponse])
async def list_igce_projects(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[IGCEProjectResponse]:
    """
    List saved IGCE projects.

    Args:
        skip: Pagination offset
        limit: Results per page
        db: Database session

    Returns:
        Paginated list of projects
    """
    try:
        # TODO: Filter by authenticated user
        result = await db.execute(
            select(IGCEProject)
            .order_by(IGCEProject.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        projects = result.scalars().all()

        count_result = await db.execute(select(IGCEProject))
        total = len(count_result.scalars().all())

        items = [
            IGCEProjectResponse(
                id=p.id,
                title=p.title,
                assumptions=p.assumptions_json,
                result=p.result_json,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
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
        logger.error("list_igce_projects_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list projects",
        )


@router.post("/projects", response_model=IGCEProjectResponse)
async def create_igce_project(
    request: IGCEProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> IGCEProjectResponse:
    """
    Save a new IGCE project.

    Args:
        request: Project creation request
        db: Database session

    Returns:
        Created project
    """
    try:
        project = IGCEProject(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),  # TODO: Get from auth
            title=request.title,
            assumptions_json=request.assumptions,
        )
        db.add(project)
        await db.commit()

        logger.info("igce_project_created", project_id=str(project.id))

        return IGCEProjectResponse(
            id=project.id,
            title=project.title,
            assumptions=project.assumptions_json,
            result=project.result_json,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    except Exception as e:
        logger.error("create_igce_project_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )


@router.get("/projects/{project_id}", response_model=IGCEProjectResponse)
async def get_igce_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IGCEProjectResponse:
    """
    Get IGCE project details.

    Args:
        project_id: Project ID
        db: Database session

    Returns:
        Project details
    """
    try:
        result = await db.execute(
            select(IGCEProject).where(IGCEProject.id == project_id)
        )
        project = result.scalars().first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        return IGCEProjectResponse(
            id=project.id,
            title=project.title,
            assumptions=project.assumptions_json,
            result=project.result_json,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_igce_project_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get project",
        )


@router.put("/projects/{project_id}", response_model=IGCEProjectResponse)
async def update_igce_project(
    project_id: uuid.UUID,
    request: IGCEProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> IGCEProjectResponse:
    """
    Update IGCE project.

    Args:
        project_id: Project ID
        request: Update request
        db: Database session

    Returns:
        Updated project
    """
    try:
        result = await db.execute(
            select(IGCEProject).where(IGCEProject.id == project_id)
        )
        project = result.scalars().first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        project.title = request.title
        project.assumptions_json = request.assumptions
        await db.commit()

        logger.info("igce_project_updated", project_id=str(project_id))

        return IGCEProjectResponse(
            id=project.id,
            title=project.title,
            assumptions=project.assumptions_json,
            result=project.result_json,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_igce_project_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project",
        )
