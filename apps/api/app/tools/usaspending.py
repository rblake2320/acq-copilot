"""USASpending API tool for federal award data queries."""

from typing import Any, Optional
from datetime import datetime
import httpx

from app.tools.base import BaseTool, Citation


class USASpendingTool(BaseTool):
    """Tool for querying federal awards, recipients, and award details from USASpending."""

    id = "usaspending.search_awards"
    name = "USASpending"
    description = "Search federal awards, award details, and recipient information from usaspending.gov"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_awards", "award_detail", "search_recipients"],
                "description": "The action to perform"
            },
            "keywords": {"type": "string", "description": "Search keywords"},
            "naics_codes": {"type": "array", "items": {"type": "string"}, "description": "NAICS codes to filter by"},
            "psc_codes": {"type": "array", "items": {"type": "string"}, "description": "PSC codes to filter by"},
            "agency": {"type": "string", "description": "Agency name or code"},
            "date_range": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                }
            },
            "award_id": {"type": "string", "description": "Award ID for detail lookup"},
            "recipient_keyword": {"type": "string", "description": "Recipient name search"},
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "awards": {"type": "array"},
            "recipients": {"type": "array"},
            "total_count": {"type": "integer"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 100}

    BASE_URL = "https://api.usaspending.gov/api/v2"

    async def run(self, params: dict) -> Any:
        """Execute USASpending search or detail lookup."""
        action = params.get("action", "").lower()
        
        if action == "search_awards":
            return await self._search_awards(params)
        elif action == "award_detail":
            return await self._get_award_detail(params)
        elif action == "search_recipients":
            return await self._search_recipients(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _search_awards(self, params: dict) -> dict:
        """Search for awards with optional filters using USASpending v2 API."""
        filters: dict = {
            "award_type_codes": ["A", "B", "C", "D"]
        }
        
        if params.get("keywords"):
            filters["keywords"] = [params["keywords"]]
        if params.get("naics_codes"):
            filters["naics_codes"] = params["naics_codes"]
        if params.get("psc_codes"):
            filters["program_codes"] = params["psc_codes"]
        if params.get("date_range"):
            dr = params["date_range"]
            filters["time_period"] = [{"start_date": dr.get("start_date"), "end_date": dr.get("end_date")}]

        body = {
            "filters": filters,
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
                       "Awarding Sub Agency", "Start Date", "End Date",
                       "Description", "naics_code", "generated_internal_id"],
            "sort": "Award Amount",
            "order": "desc",
            "limit": params.get("limit", 10),
            "page": params.get("page", 1),
        }

        url = f"{self.BASE_URL}/search/spending_by_award/"
        
        response = await self._client.post(url, json=body)
        response.raise_for_status()
        
        data = response.json()
        
        awards = []
        for result in data.get("results", []):
            internal_id = result.get("generated_internal_id", "")
            awards.append({
                "piid": result.get("Award ID", ""),
                "award_id": result.get("Award ID", internal_id),
                "award_type": "Contract",
                "recipient_name": result.get("Recipient Name", ""),
                "award_amount": float(result.get("Award Amount") or 0),
                "obligated_amount": float(result.get("Award Amount") or 0),
                "description": result.get("Description", ""),
                "period_start": result.get("Start Date"),
                "period_end": result.get("End Date"),
                "agency_name": result.get("Awarding Agency", ""),
                "sub_agency": result.get("Awarding Sub Agency", ""),
                "naics_code": result.get("naics_code"),
                "usaspending_url": f"https://www.usaspending.gov/award/{internal_id}/" if internal_id else None,
            })
        
        return {
            "awards": awards,
            "total_count": data.get("total_spending", 0),
            "page": params.get("page", 1),
            "limit": params.get("limit", 10)
        }

    async def _get_award_detail(self, params: dict) -> dict:
        """Get detailed information about a specific award."""
        award_id = params.get("award_id")
        if not award_id:
            raise ValueError("award_id is required for award_detail action")
        
        url = f"{self.BASE_URL}/awards/{award_id}/"
        
        response = await self._client.get(url)
        response.raise_for_status()
        
        data = response.json()
        results = data.get("results", {})
        
        if not results:
            raise ValueError(f"Award {award_id} not found")
        
        return {
            "piid": results.get("piid"),
            "award_id": results.get("award_id", ""),
            "award_type": results.get("type", ""),
            "recipient_name": results.get("recipient", {}).get("name", ""),
            "award_amount": float(results.get("award_amount", 0)),
            "obligated_amount": float(results.get("obligated_amount", 0)),
            "description": results.get("description", ""),
            "period_start": results.get("period_of_performance", {}).get("start_date"),
            "period_end": results.get("period_of_performance", {}).get("end_date"),
            "agency_name": results.get("agency", {}).get("name", ""),
        }

    async def _search_recipients(self, params: dict) -> dict:
        """Search for federal award recipients."""
        url = f"{self.BASE_URL}/recipient/search"
        
        query_params = {
            "keyword": params.get("recipient_keyword", ""),
            "page": params.get("page", 1),
            "limit": params.get("limit", 10),
        }
        
        response = await self._client.get(url, params=query_params)
        response.raise_for_status()
        
        data = response.json()
        
        recipients = []
        for result in data.get("results", []):
            recipients.append({
                "recipient_id": result.get("recipient_id", ""),
                "recipient_name": result.get("recipient_name", ""),
                "recipient_type": result.get("recipient_type", ""),
                "total_obligations": float(result.get("total_obligations", 0)),
                "award_count": result.get("award_count", 0),
            })
        
        return {
            "recipients": recipients,
            "total_count": data.get("total_count", 0),
            "page": params.get("page", 1),
            "limit": params.get("limit", 10)
        }

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for USASpending data."""
        citations = []
        
        action = params.get("action", "").lower()
        
        if action == "award_detail" and params.get("award_id"):
            url = f"https://www.usaspending.gov/award/{params['award_id']}/"
            citations.append(Citation(
                source_name="USASpending",
                source_url=url,
                source_label="USASpending Award Detail",
                retrieved_at=datetime.utcnow()
            ))
        else:
            citations.append(Citation(
                source_name="USASpending",
                source_url="https://www.usaspending.gov/search",
                source_label="USASpending Award Search",
                retrieved_at=datetime.utcnow()
            ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if USASpending API is available."""
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/references/toptier_agencies/",
                params={"limit": 1},
                timeout=10.0
            )
            return {
                "tool_id": self.id,
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "message": f"HTTP {response.status_code}"
            }
        except Exception as e:
            return {
                "tool_id": self.id,
                "status": "unhealthy",
                "message": str(e)
            }

    def get_examples(self) -> list[dict]:
        """Return example invocations."""
        return [
            {
                "action": "search_awards",
                "keywords": "software development",
                "agency": "Department of Defense",
                "limit": 10
            },
            {
                "action": "award_detail",
                "award_id": "CONT_AWD-0000001"
            },
            {
                "action": "search_recipients",
                "recipient_keyword": "Technology",
                "limit": 5
            }
        ]
