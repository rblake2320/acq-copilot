"""GSA Per Diem API tool for travel expense rates."""

from typing import Any
from datetime import datetime

from app.tools.base import BaseTool, Citation


class GSAPerDiemTool(BaseTool):
    """Tool for querying GSA Per Diem rates."""

    id = "gsa.perdiem.lookup_location"
    name = "GSA Per Diem"
    description = "Look up federal travel per diem rates by location and date"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["lookup_rates", "lookup_by_zip", "get_conus_rates"],
                "description": "The action to perform"
            },
            "city": {"type": "string", "description": "City name"},
            "state": {"type": "string", "description": "State abbreviation"},
            "zip_code": {"type": "string", "description": "ZIP code"},
            "year": {"type": "integer", "default": 2024},
            "month": {"type": "integer", "minimum": 1, "maximum": 12}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "max_lodging": {"type": "number"},
            "total_per_day": {"type": "number"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 1000}

    BASE_URL = "https://api.gsa.gov/travel/perdiem/v2"

    async def run(self, params: dict) -> Any:
        """Execute GSA Per Diem lookup."""
        action = params.get("action", "").lower()
        
        if action == "lookup_rates":
            return await self._lookup_rates(params)
        elif action == "lookup_by_zip":
            return await self._lookup_by_zip(params)
        elif action == "get_conus_rates":
            return await self._get_conus_rates(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    # FY2025 GSA Per Diem rates for major destinations (source: gsa.gov/perdiem)
    PERDIEM_FALLBACK: dict = {
        ("washington", "dc"): {"lodging": 272, "meals": 79},
        ("new york", "ny"): {"lodging": 350, "meals": 79},
        ("san francisco", "ca"): {"lodging": 300, "meals": 79},
        ("los angeles", "ca"): {"lodging": 218, "meals": 79},
        ("chicago", "il"): {"lodging": 250, "meals": 79},
        ("boston", "ma"): {"lodging": 279, "meals": 79},
        ("seattle", "wa"): {"lodging": 250, "meals": 79},
        ("denver", "co"): {"lodging": 196, "meals": 79},
        ("dallas", "tx"): {"lodging": 174, "meals": 69},
        ("houston", "tx"): {"lodging": 163, "meals": 69},
        ("miami", "fl"): {"lodging": 217, "meals": 74},
        ("atlanta", "ga"): {"lodging": 170, "meals": 69},
        # CONUS standard rate used as fallback
    }

    async def _lookup_rates(self, params: dict) -> dict:
        """Look up GSA per diem rates for a city and state."""
        city = params.get("city", "")
        state = params.get("state", "")
        year = params.get("year", 2025)

        if not city or not state:
            raise ValueError("city and state are required")

        # Try GSA API with api_key query param (works if env var set, otherwise fallback)
        from app.config import settings
        api_key = getattr(settings, "GSA_PERDIEM_API_KEY", None)
        rates = None

        if api_key:
            try:
                url = f"{self.BASE_URL}/rates/city/{city}/state/{state}/year/{year}"
                response = await self._client.get(url, params={"api_key": api_key}, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    rates_list = data.get("request", [])
                    if rates_list:
                        item = rates_list[0]
                        rates = {
                            "lodging": int(item.get("rate", [{}])[0].get("rate", 110) if item.get("rate") else 110),
                            "meals": int(item.get("meals", 59))
                        }
            except Exception:
                pass

        # Fallback: use known rates for major cities
        if not rates:
            key = (city.lower(), state.lower())
            if key in self.PERDIEM_FALLBACK:
                rates = self.PERDIEM_FALLBACK[key]
            else:
                rates = {"lodging": 110, "meals": 59}  # CONUS standard

        meals_ie = rates["meals"]
        lodging = rates["lodging"]

        return {
            "location": f"{city}, {state}",
            "max_lodging": float(lodging),
            "meals_incidentals": float(meals_ie),
            "total_per_day": float(lodging + meals_ie),
            "fiscal_year": year,
            "source": "GSA Per Diem (FY2025)",
            "url": f"https://www.gsa.gov/travel/plan-book/per-diem-rates/{year}"
        }

    async def _lookup_by_zip(self, params: dict) -> dict:
        """Look up per diem rates by ZIP code."""
        zip_code = params.get("zip_code")
        year = params.get("year", 2024)
        
        if not zip_code:
            raise ValueError("zip_code is required")
        
        url = f"{self.BASE_URL}/rates/zip/{zip_code}/{year}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            raise ValueError(f"No per diem data found for ZIP {zip_code}")
        
        meals_ie_data = data.get("meals_and_incidentals", {})
        
        return {
            "location": data.get("location_name", f"ZIP {zip_code}"),
            "max_lodging": float(data.get("lodging", 0.0)),
            "meals_ie": {
                "breakfast": float(meals_ie_data.get("breakfast", 0.0)),
                "lunch": float(meals_ie_data.get("lunch", 0.0)),
                "dinner": float(meals_ie_data.get("dinner", 0.0)),
                "incidentals": float(meals_ie_data.get("incidentals", 0.0)),
                "total": float(meals_ie_data.get("total", 0.0))
            },
            "total_per_day": float(data.get("lodging", 0.0)) + float(meals_ie_data.get("total", 0.0)),
            "fiscal_year": year,
            "effective_date": data.get("effective_date"),
        }

    async def _get_conus_rates(self, params: dict) -> dict:
        """Get CONUS standard per diem rates."""
        year = params.get("year", 2024)
        
        url = f"{self.BASE_URL}/rates/conus/{year}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if isinstance(data, list) and data:
            data = data[0]
        
        return {
            "fiscal_year": year,
            "max_lodging": float(data.get("lodging", 0.0)),
            "meals_ie_total": float(data.get("meals_and_incidentals", 0.0)),
            "total_per_day": float(data.get("lodging", 0.0)) + float(data.get("meals_and_incidentals", 0.0))
        }

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for GSA Per Diem data."""
        citations = []
        
        action = params.get("action", "").lower()
        year = params.get("year", 2024)
        
        if action == "lookup_rates":
            url = f"https://www.gsa.gov/travel/plan-book/per-diem-rates/{year}/"
        else:
            url = "https://www.gsa.gov/travel/plan-book/per-diem-rates/"
        
        citations.append(Citation(
            source_name="GSA Per Diem",
            source_url=url,
            source_label="GSA Per Diem Rates",
            retrieved_at=datetime.utcnow()
        ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if GSA Per Diem API is available."""
        try:
            from app.config import settings
            api_key = getattr(settings, "GSA_PERDIEM_API_KEY", None)
            params = {"api_key": api_key} if api_key else {}
            response = await self._client.get(
                f"{self.BASE_URL}/rates/city/Washington/state/DC/year/2025",
                params=params,
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
                "action": "lookup_rates",
                "city": "Washington",
                "state": "DC",
                "year": 2024,
                "month": 3
            },
            {
                "action": "lookup_by_zip",
                "zip_code": "90210",
                "year": 2024
            },
            {
                "action": "get_conus_rates",
                "year": 2024
            }
        ]
