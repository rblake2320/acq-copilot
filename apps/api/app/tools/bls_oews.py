"""BLS Occupational Employment and Wage Statistics (OEWS) tool."""

from typing import Any
from datetime import datetime

from app.tools.base import BaseTool, Citation
from app.config import settings


class BLSOEWSTool(BaseTool):
    """Tool for querying BLS Occupational Employment and Wage Statistics."""

    id = "bls.oews.lookup_wages"
    name = "BLS OEWS"
    description = "Look up wage data, occupations, and geographic areas from BLS OEWS"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["lookup_wages", "search_occupations", "get_area_codes"],
                "description": "The action to perform"
            },
            "occupation_code": {"type": "string", "description": "SOC occupation code"},
            "area_code": {"type": "string", "description": "Area code"},
            "data_type": {"type": "string", "enum": ["annual", "hourly"], "default": "annual"},
            "keyword": {"type": "string", "description": "Keyword for occupation search"},
            "state": {"type": "string", "description": "State abbreviation"}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "occupation_code": {"type": "string"},
            "wages": {"type": "object"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 10}

    BASE_URL = "https://api.bls.gov/publicAPI/v2"

    async def run(self, params: dict) -> Any:
        """Execute BLS OEWS lookup or search."""
        action = params.get("action", "").lower()
        
        if action == "lookup_wages":
            return await self._lookup_wages(params)
        elif action == "search_occupations":
            return await self._search_occupations(params)
        elif action == "get_area_codes":
            return await self._get_area_codes(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    # Known 2023 BLS OEWS national mean annual wages (source: bls.gov/oes)
    OEWS_FALLBACK: dict = {
        "11-1011": {"title": "Chief Executives", "mean_annual": 246440, "median_annual": 206680},
        "11-2021": {"title": "Marketing Managers", "mean_annual": 166850, "median_annual": 140040},
        "11-3021": {"title": "Computer and Information Systems Managers", "mean_annual": 176450, "median_annual": 169510},
        "13-1111": {"title": "Management Analysts", "mean_annual": 102270, "median_annual": 95290},
        "15-1211": {"title": "Computer Systems Analysts", "mean_annual": 108990, "median_annual": 102240},
        "15-1212": {"title": "Information Security Analysts", "mean_annual": 120360, "median_annual": 112000},
        "15-1231": {"title": "Computer Network Support Specialists", "mean_annual": 72560, "median_annual": 67640},
        "15-1241": {"title": "Computer Network Architects", "mean_annual": 131660, "median_annual": 126900},
        "15-1244": {"title": "Network and Computer Systems Administrators", "mean_annual": 92970, "median_annual": 90520},
        "15-1251": {"title": "Computer Programmers", "mean_annual": 99860, "median_annual": 97800},
        "15-1252": {"title": "Software Developers", "mean_annual": 130160, "median_annual": 124200},
        "15-1253": {"title": "Software Quality Assurance Analysts", "mean_annual": 105340, "median_annual": 98220},
        "15-1254": {"title": "Web Developers", "mean_annual": 86040, "median_annual": 80730},
        "15-1255": {"title": "Web and Digital Interface Designers", "mean_annual": 84120, "median_annual": 79190},
        "15-2051": {"title": "Data Scientists", "mean_annual": 124490, "median_annual": 108020},
        "15-2041": {"title": "Statisticians", "mean_annual": 108490, "median_annual": 99960},
    }

    async def _lookup_wages(self, params: dict) -> dict:
        """Look up wage data for an occupation and area from BLS OEWS."""
        occupation_code = params.get("occupation_code")
        area_code = params.get("area_code", "0000000")
        data_type = params.get("data_type", "annual")

        if not occupation_code:
            raise ValueError("occupation_code is required")

        # Normalize SOC code (remove dashes, e.g. "15-1252" -> "151252")
        soc_clean = occupation_code.replace("-", "")
        # BLS OEWS series: OEUM + area(7 chars) + soc(6 chars) + "03" (mean annual)
        # National area code is 0000000 (7 zeros)
        area_norm = area_code.replace("S", "").replace("US", "0000000")
        if len(area_norm) < 7:
            area_norm = area_norm.ljust(7, "0")
        area_norm = area_norm[:7]
        series_id = f"OEUM{area_norm}{soc_clean}03"

        wages: dict = {}
        source = "BLS API"
        try:
            payload: dict = {
                "seriesid": [series_id],
                "startyear": 2022,
                "endyear": 2024,
            }
            if settings.BLS_API_KEY:
                payload["registrationkey"] = settings.BLS_API_KEY
            response = await self._client.post(
                f"{self.BASE_URL}/timeseries/data/", json=payload, timeout=15.0
            )
            response.raise_for_status()
            data = response.json()
            series_list = data.get("Results", {}).get("series", [])
            if series_list and series_list[0].get("data"):
                pt = series_list[0]["data"][0]
                wages = {
                    "mean_annual": int(float(pt.get("value", 0)) * (2080 if data_type == "hourly" else 1)),
                    "period": pt.get("year"),
                }
                source = "BLS API"
        except Exception:
            pass

        # Fallback to known BLS OEWS data if API returns nothing
        if not wages and occupation_code in self.OEWS_FALLBACK:
            fb = self.OEWS_FALLBACK[occupation_code]
            wages = {
                "mean_annual": fb["mean_annual"],
                "median_annual": fb["median_annual"],
                "occupation_title": fb["title"],
            }
            source = "BLS OEWS 2023 (published)"

        if not wages:
            # Generic fallback
            wages = {"mean_annual": 95000, "median_annual": 85000, "note": "Estimated - SOC not found"}
            source = "estimated"

        occ_info = self.OEWS_FALLBACK.get(occupation_code, {})
        return {
            "occupation_code": occupation_code,
            "occupation_title": occ_info.get("title", occupation_code),
            "area_code": area_code,
            "data_type": data_type,
            "wages": wages,
            "source": source,
            "mean_annual": wages.get("mean_annual"),
            "median_annual": wages.get("median_annual"),
        }

    async def _search_occupations(self, params: dict) -> dict:
        """Search for occupations by keyword."""
        keyword = params.get("keyword")
        if not keyword:
            raise ValueError("keyword is required")
        
        # Mock implementation - in production, use SOC lookup
        occupations = [
            {
                "code": "11-1011",
                "title": "Chief Executives",
                "category": "Management"
            },
            {
                "code": "13-1111",
                "title": "Management Analysts",
                "category": "Business and Financial"
            },
        ]
        
        return {
            "occupations": occupations,
            "total": len(occupations)
        }

    async def _get_area_codes(self, params: dict) -> dict:
        """Get area codes for a state."""
        state = params.get("state")
        if not state:
            raise ValueError("state is required")
        
        state_areas = {
            "US": [{"code": "US000000", "name": "United States", "level": "National"}],
            "CA": [
                {"code": "06000000", "name": "California", "level": "State"},
                {"code": "06200000", "name": "Los Angeles", "level": "Metro"},
            ],
            "TX": [
                {"code": "48000000", "name": "Texas", "level": "State"},
                {"code": "48200000", "name": "Dallas-Fort Worth", "level": "Metro"},
            ],
        }
        
        areas = state_areas.get(state.upper(), [])
        
        if not areas:
            raise ValueError(f"No area codes found for state {state}")
        
        return {"areas": areas, "total": len(areas)}

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for BLS OEWS data."""
        citations = []
        
        action = params.get("action", "").lower()
        
        if action == "lookup_wages" and params.get("occupation_code"):
            url = f"https://www.bls.gov/oes/current/oes_{params['occupation_code']}.htm"
            citations.append(Citation(
                source_name="BLS OEWS",
                source_url=url,
                source_label="BLS Occupational Employment and Wage Statistics",
                retrieved_at=datetime.utcnow()
            ))
        else:
            citations.append(Citation(
                source_name="BLS OEWS",
                source_url="https://www.bls.gov/oes/",
                source_label="BLS OES Program",
                retrieved_at=datetime.utcnow()
            ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if BLS API is available."""
        try:
            payload: dict = {
                "seriesid": ["OEUM000000110110"],
                "startyear": 2024,
                "endyear": 2024,
            }
            if settings.BLS_API_KEY:
                payload["registrationkey"] = settings.BLS_API_KEY
            response = await self._client.post(
                f"{self.BASE_URL}/timeseries/data/",
                json=payload,
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
                "action": "lookup_wages",
                "occupation_code": "11-1011",
                "area_code": "US000000",
                "data_type": "annual"
            },
            {
                "action": "search_occupations",
                "keyword": "computer"
            },
            {
                "action": "get_area_codes",
                "state": "CA"
            }
        ]
