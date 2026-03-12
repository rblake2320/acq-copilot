"""SAM.gov Opportunities tool — searches federal contract opportunities."""

from datetime import datetime, timedelta
from typing import Optional, Any
from pydantic import BaseModel
import structlog

from .base import BaseTool, Citation

logger = structlog.get_logger(__name__)

SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"


class OpportunityResult(BaseModel):
    notice_id: str
    title: str
    solicitation_number: Optional[str] = None
    posted_date: Optional[str] = None
    response_deadline: Optional[str] = None
    agency: str
    office: Optional[str] = None
    naics_code: Optional[str] = None
    set_aside: Optional[str] = None
    place_of_performance: Optional[str] = None
    contract_type: Optional[str] = None
    description: Optional[str] = None
    active: bool = True
    sam_url: str


class SamSearchOutput(BaseModel):
    opportunities: list[OpportunityResult]
    total_records: int
    query: str
    filters_applied: dict
    api_key_configured: bool = False


class SamSearchTool(BaseTool):
    """Search SAM.gov for federal contract opportunities."""

    id = "sam.search_opportunities"
    name = "SAM.gov Opportunity Search"
    description = (
        "Search SAM.gov for active federal contract opportunities. "
        "Filter by keywords, NAICS code, set-aside type, location, or agency."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword search"},
            "naics_code": {"type": "string", "description": "NAICS code filter"},
            "state": {"type": "string", "description": "2-letter state code"},
            "agency": {"type": "string", "description": "Agency name filter"},
            "set_aside": {
                "type": "string",
                "description": "Set-aside type (e.g. 'SBA', '8A', 'HZC', 'SDVOSBC', 'WOSB')",
            },
            "limit": {"type": "integer", "default": 10, "maximum": 25},
        },
        "required": [],
    }
    output_schema = {"type": "object"}
    auth_requirements = ["SAM_API_KEY (optional — free at api.data.gov)"]
    rate_limit_profile = {"requests_per_minute": 100}

    async def run(self, params: dict) -> Any:
        """Execute SAM.gov opportunity search."""
        import os

        query = params.get("query", "")
        naics = params.get("naics_code", "")
        state = params.get("state", "")
        set_aside = params.get("set_aside", "")
        limit = min(params.get("limit", 10), 25)

        # Resolve API key: params override → env → settings
        api_key = params.get("api_key", "")
        if not api_key:
            # Try settings first, fall back to raw env
            try:
                from ..config import settings
                api_key = getattr(settings, "SAM_API_KEY", "") or ""
            except Exception:
                pass
        if not api_key:
            api_key = os.environ.get("SAM_API_KEY", "")

        if not api_key:
            return self._no_api_key_output(query)

        # Date range: last 90 days by default
        posted_from = (datetime.utcnow() - timedelta(days=90)).strftime("%m/%d/%Y")
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")

        request_params: dict[str, Any] = {
            "api_key": api_key,
            "limit": limit,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "active": "Yes",
        }

        if query:
            request_params["q"] = query
        if naics:
            request_params["naicsCode"] = naics
        if state:
            request_params["placeOfPerformanceState"] = state
        if set_aside:
            request_params["ntype"] = set_aside

        response = await self._client.get(
            SAM_API_BASE,
            params=request_params,
            timeout=15.0,
            headers={"Accept": "application/json"},
        )

        if response.status_code == 403:
            logger.warning("sam_api_key_invalid_or_missing")
            return self._no_api_key_output(query)

        response.raise_for_status()
        data = response.json()
        opportunities = self._parse_opportunities(data)

        return SamSearchOutput(
            opportunities=opportunities,
            total_records=data.get("totalRecords", len(opportunities)),
            query=query,
            filters_applied={
                k: v
                for k, v in {
                    "naics_code": naics,
                    "state": state,
                    "set_aside": set_aside,
                }.items()
                if v
            },
            api_key_configured=True,
        ).model_dump()

    def _parse_opportunities(self, data: dict) -> list[OpportunityResult]:
        """Parse SAM.gov API response into OpportunityResult objects."""
        opps = []
        for item in data.get("opportunitiesData", []):
            notice_id = item.get("noticeId", "unknown")
            desc_raw = item.get("description", "")
            opps.append(
                OpportunityResult(
                    notice_id=notice_id,
                    title=item.get("title", "Untitled"),
                    solicitation_number=item.get("solicitationNumber"),
                    posted_date=item.get("postedDate"),
                    response_deadline=item.get("responseDeadLine"),
                    agency=item.get(
                        "fullParentPathName",
                        item.get("departmentName", "Unknown Agency"),
                    ),
                    office=item.get("organizationName"),
                    naics_code=item.get("naicsCode"),
                    set_aside=item.get("typeOfSetAsideDescription"),
                    place_of_performance=self._format_location(
                        item.get("placeOfPerformance", {})
                    ),
                    contract_type=item.get("type"),
                    description=desc_raw[:500] if desc_raw else None,
                    active=item.get("active", "Yes").upper() == "YES",
                    sam_url=f"https://sam.gov/opp/{notice_id}/view",
                )
            )
        return opps

    def _format_location(self, location: dict) -> Optional[str]:
        if not location:
            return None
        city = location.get("city", {}).get("name", "")
        state = location.get("state", {}).get("code", "")
        if city and state:
            return f"{city}, {state}"
        return state or city or None

    def _no_api_key_output(self, query: str) -> dict:
        """Return structured output when no valid SAM.gov API key is configured."""
        return SamSearchOutput(
            opportunities=[],
            total_records=0,
            query=query,
            filters_applied={},
            api_key_configured=False,
        ).model_dump()

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for SAM.gov opportunity data."""
        query = params.get("query", "")
        search_url = f"https://sam.gov/search/?keywords={query}&index=opp" if query else "https://sam.gov/search/?index=opp"

        # Check whether we got real results
        api_configured = False
        if isinstance(output, dict):
            api_configured = output.get("api_key_configured", False)
            total = output.get("total_records", 0)
        else:
            total = 0

        if api_configured:
            snippet = f"Found {total} active opportunities on SAM.gov"
            if query:
                snippet += f" matching '{query}'"
        else:
            snippet = "Get a free SAM.gov API key at api.data.gov to enable live opportunity search"

        return [
            Citation(
                source_name="SAM.gov Federal Opportunities",
                source_url=search_url,
                source_label="SAM.gov — System for Award Management",
                retrieved_at=datetime.utcnow(),
                snippet=snippet,
            )
        ]

    async def healthcheck(self) -> dict[str, Any]:
        """Check SAM.gov API reachability (unauthenticated ping)."""
        try:
            response = await self._client.get(
                SAM_API_BASE,
                params={"limit": 1, "postedFrom": "01/01/2024", "postedTo": "01/02/2024"},
                timeout=8.0,
                headers={"Accept": "application/json"},
            )
            # 403 = reachable but no key (expected without key); 200 = key present and valid
            if response.status_code in (200, 403):
                return {"tool_id": self.id, "status": "healthy", "message": f"HTTP {response.status_code}"}
            return {"tool_id": self.id, "status": "unhealthy", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"tool_id": self.id, "status": "unhealthy", "message": str(e)}

    def get_examples(self) -> list[dict]:
        """Return example invocations."""
        return [
            {"query": "software development", "naics_code": "541511", "limit": 10},
            {"query": "cybersecurity", "set_aside": "SBA", "limit": 5},
            {"query": "logistics", "state": "VA", "limit": 10},
        ]
