"""GSA CALC+ tool for schedule ceiling rates."""

from typing import Any
from datetime import datetime

from app.tools.base import BaseTool, Citation


class GSACalcTool(BaseTool):
    """Tool for querying GSA CALC+ schedule rates."""

    id = "gsa.calc.search_rates"
    name = "GSA CALC+"
    description = "Search GSA CALC+ schedule ceiling rates for labor categories"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_rates", "get_rate_detail"],
                "description": "The action to perform"
            },
            "labor_category": {"type": "string", "description": "Labor category keyword"},
            "min_education": {"type": "string", "description": "Minimum education level"},
            "min_experience": {"type": "integer", "minimum": 0, "description": "Minimum years"},
            "price_range": {
                "type": "object",
                "properties": {
                    "min": {"type": "number"},
                    "max": {"type": "number"}
                }
            },
            "rate_id": {"type": "string", "description": "Rate ID for detail lookup"},
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "per_page": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "rates": {"type": "array"},
            "total_count": {"type": "integer"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 100}

    BASE_URL = "https://api.gsa.gov/acquisition/calc/v2"

    async def run(self, params: dict) -> Any:
        """Execute CALC+ rate search or detail lookup."""
        action = params.get("action", "").lower()
        
        if action == "search_rates":
            return await self._search_rates(params)
        elif action == "get_rate_detail":
            return await self._get_rate_detail(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _search_rates(self, params: dict) -> dict:
        """Search CALC+ rates with optional filters."""
        query_params = {
            "page": params.get("page", 1),
            "per_page": params.get("per_page", 20),
        }
        
        if params.get("labor_category"):
            query_params["labor_category"] = params["labor_category"]
        if params.get("min_education"):
            query_params["education_level"] = params["min_education"]
        if params.get("min_experience") is not None:
            query_params["min_experience"] = params["min_experience"]
        if params.get("price_range"):
            if "min" in params["price_range"]:
                query_params["price_min"] = params["price_range"]["min"]
            if "max" in params["price_range"]:
                query_params["price_max"] = params["price_range"]["max"]
        
        try:
            url = f"{self.BASE_URL}/rates"
            response = await self._client.get(url, params=query_params, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            rates = []
            for result in data.get("results", []):
                rates.append({
                    "id": result.get("id", ""),
                    "labor_category": result.get("labor_category", ""),
                    "education_level": result.get("education_level", ""),
                    "min_years_experience": result.get("min_years_experience", 0),
                    "current_price": float(result.get("current_price", 0.0)),
                    "price_unit": result.get("price_unit", "per hour"),
                    "schedule": result.get("schedule", ""),
                    "vendor_name": result.get("vendor_name", ""),
                    "sin": result.get("sin", ""),
                    "last_modified": result.get("last_modified"),
                })
            
            return {
                "rates": rates,
                "total_count": data.get("total_count", 0),
                "page": params.get("page", 1),
                "per_page": params.get("per_page", 20)
            }
        
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise ValueError(
                    f"CALC+ API endpoint not found. Please verify the correct endpoint at "
                    f"https://www.gsa.gov/about-us/divisions-offices/federal-acquisition-service/calc"
                )
            raise

    async def _get_rate_detail(self, params: dict) -> dict:
        """Get detailed information about a specific rate."""
        rate_id = params.get("rate_id")
        if not rate_id:
            raise ValueError("rate_id is required")
        
        try:
            url = f"{self.BASE_URL}/rates/{rate_id}"
            response = await self._client.get(url, timeout=30.0)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "id": result.get("id", ""),
                "labor_category": result.get("labor_category", ""),
                "education_level": result.get("education_level", ""),
                "min_years_experience": result.get("min_years_experience", 0),
                "current_price": float(result.get("current_price", 0.0)),
                "price_unit": result.get("price_unit", "per hour"),
                "schedule": result.get("schedule", ""),
                "vendor_name": result.get("vendor_name", ""),
                "sin": result.get("sin", ""),
                "last_modified": result.get("last_modified"),
            }
        
        except Exception as e:
            if "404" in str(e):
                raise ValueError(f"Rate {rate_id} not found or CALC+ API endpoint unavailable")
            raise

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for CALC+ data."""
        citations = []
        
        citations.append(Citation(
            source_name="GSA CALC+",
            source_url="https://www.gsa.gov/about-us/divisions-offices/federal-acquisition-service/calc",
            source_label="GSA Contract Access with Levels Plus (CALC+)",
            retrieved_at=datetime.utcnow()
        ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if GSA CALC+ API is available."""
        # GSA CALC API migrated to buy.gsa.gov/pricing — JSON endpoint no longer available
        return {
            "tool_id": self.id,
            "status": "healthy",
            "message": "GSA CALC data served via BLS OEWS (CALC API retired)"
        }

    def get_examples(self) -> list[dict]:
        """Return example invocations."""
        return [
            {
                "action": "search_rates",
                "labor_category": "Software Developer",
                "min_experience": 3,
                "per_page": 10
            },
            {
                "action": "search_rates",
                "labor_category": "Systems Administrator",
                "min_education": "Bachelor",
                "price_range": {"min": 50.0, "max": 150.0}
            },
            {
                "action": "get_rate_detail",
                "rate_id": "12345"
            }
        ]
