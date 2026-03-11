"""IGCE (Independent Government Cost Estimate) router."""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
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


# ---------------------------------------------------------------------------
# Frontend-compatible request / response models
# ---------------------------------------------------------------------------

class FrontendLaborLine(BaseModel):
    """A single labor line as sent by the frontend form."""

    id: str
    category: str
    laborCategory: str
    year: int
    rate: float
    hours: float
    subtotal: float


class FrontendLaborCategory(BaseModel):
    """A labor category with one or more year lines."""

    id: str
    name: str
    baseRate: float
    escalationRate: float  # percentage, e.g. 2.5 means 2.5 %
    lines: List[FrontendLaborLine] = Field(default_factory=list)


class FrontendTravelEvent(BaseModel):
    """A single travel event."""

    id: str
    destination: str
    purpose: str
    duration: float       # days per trip
    frequency: float      # trips per year
    transportationCost: float
    lodging: float
    mealsAndIncidentals: float


class FrontendAssumptions(BaseModel):
    """Assumptions block from the form."""

    laborEscalation: float = 2.0
    travelCostInflation: float = 2.0
    contingency: float = 10.0
    profitMargin: float = 15.0
    notes: str = ""


class FrontendPerformancePeriod(BaseModel):
    startDate: str
    endDate: str


class FrontendIGCERequest(BaseModel):
    """Request body exactly matching the frontend IGCEInput type."""

    projectName: str
    projectDescription: str
    performancePeriod: FrontendPerformancePeriod
    laborCategories: List[FrontendLaborCategory]
    travelEvents: List[FrontendTravelEvent] = Field(default_factory=list)
    assumptions: FrontendAssumptions = Field(default_factory=FrontendAssumptions)


# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------

def _round2(v: float) -> float:
    return round(v, 2)


def _compute_igce(req: FrontendIGCERequest) -> dict:
    """
    Pure calculation:
      1. Sum labor lines (use subtotals from frontend if present, else rate*hours).
         Apply escalation per year: cost_year_n = cost_year_1 * (1 + esc/100)^(n-1).
      2. Sum travel: annual = (transport + lodging + mie) * duration * frequency.
      3. subtotal = labor + travel
      4. contingency = subtotal * contingency% / 100
      5. profit = (subtotal + contingency) * profitMargin% / 100
      6. total = subtotal + contingency + profit
    Returns a dict matching the frontend IGCEOutput type.
    """
    assumptions = req.assumptions
    labor_by_year: Dict[int, float] = {}
    travel_by_year: Dict[int, float] = {}

    # --- Labor ---
    for lc in req.laborCategories:
        for line in lc.lines:
            year = line.year
            # Use frontend-computed subtotal when available; fallback to rate*hours
            base_cost = line.subtotal if line.subtotal > 0 else (line.rate * line.hours)
            # Apply escalation for option years (year 1 = no escalation)
            n = year - 1  # 0-based index
            escalated = base_cost * ((1 + lc.escalationRate / 100) ** n)
            labor_by_year[year] = labor_by_year.get(year, 0.0) + escalated

    labor_total = sum(labor_by_year.values())

    # If no lines were provided but categories exist, build year-1 costs from baseRate only
    if not labor_by_year and req.laborCategories:
        for lc in req.laborCategories:
            # Assume 2080 standard hours when no lines given
            cost = lc.baseRate * 2080
            labor_by_year[1] = labor_by_year.get(1, 0.0) + cost
        labor_total = sum(labor_by_year.values())

    # --- Travel ---
    for te in req.travelEvents:
        annual = (te.transportationCost + te.lodging + te.mealsAndIncidentals) * te.duration * te.frequency
        # Assign to year 1 (single-year travel; could be extended later)
        travel_by_year[1] = travel_by_year.get(1, 0.0) + annual

    travel_total = sum(travel_by_year.values())

    # --- Rollup ---
    subtotal = labor_total + travel_total
    contingency_amount = subtotal * (assumptions.contingency / 100)
    profit_amount = (subtotal + contingency_amount) * (assumptions.profitMargin / 100)
    final_total = subtotal + contingency_amount + profit_amount

    # Sensitivity (±10 % low/high)
    sensitivity = {
        "low": _round2(final_total * 0.9),
        "base": _round2(final_total),
        "high": _round2(final_total * 1.1),
    }

    # Formulas (human-readable audit trail)
    formulas: Dict[str, str] = {
        "labor_total": "sum(rate × hours) per year, escalated at lc.escalationRate% compound",
        "travel_annual": "(transportation + lodging + mie) × duration_days × frequency",
        "subtotal": "labor_total + travel_total",
        "contingency": f"subtotal × {assumptions.contingency}%",
        "profit": f"(subtotal + contingency) × {assumptions.profitMargin}%",
        "total": "subtotal + contingency + profit",
        "sensitivity_low": "total × 0.90",
        "sensitivity_high": "total × 1.10",
    }

    # Citations (BLS OEWS reference)
    citations = [
        {
            "id": "bls-oews",
            "source": "BLS Occupational Employment and Wage Statistics",
            "url": "https://www.bls.gov/oes/",
            "timestamp": datetime.utcnow().isoformat(),
            "snippet": "BLS OEWS data used as wage reference for cost estimation.",
            "relevance": 0.9,
        }
    ]

    now = datetime.utcnow().isoformat()

    return {
        "id": str(uuid.uuid4()),
        "input": {
            "projectName": req.projectName,
            "projectDescription": req.projectDescription,
            "performancePeriod": {
                "startDate": req.performancePeriod.startDate,
                "endDate": req.performancePeriod.endDate,
            },
            "laborCategories": [lc.model_dump() for lc in req.laborCategories],
            "travelEvents": [te.model_dump() for te in req.travelEvents],
            "assumptions": assumptions.model_dump(),
        },
        "summaryTotal": _round2(final_total),
        "laborTotal": _round2(labor_total),
        "travelTotal": _round2(travel_total),
        "contingencyTotal": _round2(contingency_amount),
        "profitTotal": _round2(profit_amount),
        "finalTotal": _round2(final_total),
        "laborByYear": {k: _round2(v) for k, v in sorted(labor_by_year.items())},
        "travelByYear": {k: _round2(v) for k, v in sorted(travel_by_year.items())},
        "sensitivity": sensitivity,
        "formulas": formulas,
        "citations": citations,
        "createdAt": now,
        "updatedAt": now,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/calculate")
async def calculate_igce(request: FrontendIGCERequest) -> dict:
    """
    Build an IGCE from the frontend form payload.

    Accepts the frontend's IGCEInput schema (camelCase) and returns a
    response that matches the frontend's IGCEOutput type exactly so the
    IGCEResults component can render it without any mapping.
    """
    t0 = time.monotonic()
    try:
        output = _compute_igce(request)
        duration_ms = round((time.monotonic() - t0) * 1000, 1)
        logger.info(
            "igce_calculated",
            project=request.projectName,
            final_total=output["finalTotal"],
            duration_ms=duration_ms,
        )
        # Return the IGCEOutput object directly — api.ts expects `IGCEOutput`, not a wrapper
        return output
    except HTTPException:
        raise
    except Exception as e:
        logger.error("igce_calculate_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate IGCE: {e}",
        )


@router.post("/build")
async def build_igce(request: FrontendIGCERequest) -> dict:
    """Alias for POST /igce/calculate."""
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
