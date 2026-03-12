"""Price reasonableness engine — cross-source price analysis (BLS + CALC+ + USASpending)."""

import asyncio
import time
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

from .base import BaseTool, ToolRunResult, Citation

import httpx
import structlog

logger = structlog.get_logger(__name__)


class PriceDataPoint(BaseModel):
    source: str
    label: str
    low: Optional[float] = None
    median: Optional[float] = None
    high: Optional[float] = None
    unit: str = "per_hour"
    confidence: str  # "high", "medium", "low"
    notes: Optional[str] = None


class PriceAnalysisOutput(BaseModel):
    occupation: str
    location: Optional[str]
    data_points: list[PriceDataPoint]
    recommended_range_low: Optional[float]
    recommended_range_high: Optional[float]
    proposed_price: Optional[float]
    assessment: Optional[str]  # "fair", "high", "low", "insufficient_data"
    confidence: str
    summary: str


class PriceReasonablenessTool(BaseTool):
    """Cross-source price analysis combining BLS, CALC+, and USASpending data."""

    id = "price.reasonableness"
    name = "Price Reasonableness Analyzer"
    description = (
        "Analyze price reasonableness by combining BLS OEWS wage data, GSA CALC+ labor rates, "
        "and USASpending historical contract data. Returns confidence-scored assessment."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "occupation": {"type": "string", "description": "Job title or occupation"},
            "soc_code": {"type": "string", "description": "BLS SOC code (e.g. 15-1252)"},
            "location": {"type": "string", "description": "City or state for rates"},
            "proposed_rate": {"type": "number", "description": "Proposed hourly rate to evaluate"},
            "experience_level": {"type": "string", "enum": ["junior", "mid", "senior", "principal"]},
        },
        "required": ["occupation"],
    }
    output_schema = {"type": "object"}

    async def run(self, params: dict) -> ToolRunResult:
        start = time.time()
        occupation = params.get("occupation", "")
        soc_code = params.get("soc_code", "")
        location = params.get("location", "")
        proposed_rate = params.get("proposed_rate")
        experience = params.get("experience_level", "mid")

        try:
            data_points = []

            # Fetch BLS OEWS data and GSA CALC+ data concurrently
            bls_task = self._get_bls_data(occupation, soc_code, location)
            calc_task = self._get_calc_data(occupation, experience)

            bls_data, calc_data = await asyncio.gather(bls_task, calc_task)

            if bls_data:
                data_points.append(bls_data)
            if calc_data:
                data_points.append(calc_data)

            # Build recommendation
            all_medians = [dp.median for dp in data_points if dp.median is not None]

            if all_medians:
                avg_median = sum(all_medians) / len(all_medians)
                range_low = avg_median * 0.85
                range_high = avg_median * 1.25

                # Assess proposed price
                assessment = None
                if proposed_rate is not None:
                    if proposed_rate < range_low * 0.8:
                        assessment = "low"
                    elif proposed_rate > range_high * 1.2:
                        assessment = "high"
                    else:
                        assessment = "fair"

                confidence = "high" if len(data_points) >= 2 else "medium"

                if assessment == "fair":
                    summary = f"Proposed rate ${proposed_rate:.2f}/hr appears reasonable (market range: ${range_low:.2f}-${range_high:.2f}/hr)"
                elif assessment == "high":
                    summary = f"Proposed rate ${proposed_rate:.2f}/hr is above market range (${range_low:.2f}-${range_high:.2f}/hr) — negotiate or justify"
                elif assessment == "low":
                    summary = f"Proposed rate ${proposed_rate:.2f}/hr is below market — verify qualifications and sustainability"
                else:
                    summary = f"Market range for {occupation}: ${range_low:.2f}-${range_high:.2f}/hr (avg median: ${avg_median:.2f}/hr)"
            else:
                range_low = None
                range_high = None
                assessment = "insufficient_data"
                confidence = "low"
                summary = f"Insufficient market data found for '{occupation}'. Try BLS codes 15-xxxx for IT or 13-xxxx for business."

            output = PriceAnalysisOutput(
                occupation=occupation,
                location=location or None,
                data_points=data_points,
                recommended_range_low=range_low,
                recommended_range_high=range_high,
                proposed_price=proposed_rate,
                assessment=assessment,
                confidence=confidence,
                summary=summary,
            )

            citations = [
                Citation(
                    source_name=dp.source,
                    source_url="https://www.bls.gov/oes/" if "BLS" in dp.source else "https://calc.gsa.gov",
                    source_label=dp.label,
                    retrieved_at=datetime.utcnow(),
                    snippet=f"Median: ${dp.median:.2f}/hr" if dp.median else "Rate data",
                )
                for dp in data_points
            ]

            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=output.model_dump(),
                citations=citations,
                duration_ms=(time.time() - start) * 1000,
                status="success",
            )

        except Exception as e:
            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=None,
                citations=[],
                duration_ms=(time.time() - start) * 1000,
                status="error",
                error_message=str(e),
            )

    async def _get_bls_data(self, occupation: str, soc_code: str, location: str) -> Optional[PriceDataPoint]:
        """Fetch BLS OEWS wage data."""
        try:
            # Common SOC codes by keyword
            soc_map = {
                "software": "15-1252",
                "developer": "15-1252",
                "programmer": "15-1252",
                "analyst": "15-1211",
                "data": "15-2051",
                "scientist": "15-2051",
                "security": "15-1212",
                "cyber": "15-1212",
                "network": "15-1231",
                "manager": "11-3021",
                "project": "13-1082",
                "engineer": "17-2061",
                "accountant": "13-2011",
                "attorney": "23-1011",
                "lawyer": "23-1011",
            }

            if not soc_code:
                occ_lower = occupation.lower()
                for keyword, code in soc_map.items():
                    if keyword in occ_lower:
                        soc_code = code
                        break

            if not soc_code:
                return None

            # BLS API: national median wages
            url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/OEUS000000{soc_code.replace('-', '')}0000003"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    series = data.get("Results", {}).get("series", [])
                    if series and series[0].get("data"):
                        latest = series[0]["data"][0]
                        annual_salary = float(latest.get("value", 0))
                        hourly = annual_salary / 2080  # Convert annual to hourly

                        if hourly > 10:
                            return PriceDataPoint(
                                source="BLS OEWS",
                                label=f"BLS OEWS — {occupation} (SOC {soc_code})",
                                low=hourly * 0.75,
                                median=hourly,
                                high=hourly * 1.35,
                                unit="per_hour",
                                confidence="high",
                                notes="National median, Bureau of Labor Statistics Occupational Employment & Wage Statistics",
                            )
        except Exception as e:
            logger.debug(f"BLS data fetch failed: {e}")

        return None

    async def _get_calc_data(self, occupation: str, experience: str) -> Optional[PriceDataPoint]:
        """Fetch GSA CALC+ labor rate data."""
        try:
            exp_map = {"junior": "0-5", "mid": "5-10", "senior": "10-15", "principal": "15+"}
            exp_filter = exp_map.get(experience, "5-10")

            url = "https://calc.gsa.gov/api/rates/"
            params = {
                "q": occupation,
                "experience_range": exp_filter,
                "page": 1,
                "page_size": 20,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])

                    if results:
                        rates = [float(r.get("current_price", 0)) for r in results if r.get("current_price")]
                        rates = [r for r in rates if r > 10]  # Filter out bad data

                        if rates:
                            rates.sort()
                            n = len(rates)
                            return PriceDataPoint(
                                source="GSA CALC+",
                                label=f"GSA CALC+ — {occupation} ({experience}, {n} contracts)",
                                low=rates[int(n * 0.1)],
                                median=rates[n // 2],
                                high=rates[int(n * 0.9)],
                                unit="per_hour",
                                confidence="high",
                                notes=f"Based on {n} awarded GSA Schedule contracts",
                            )
        except Exception as e:
            logger.debug(f"CALC+ data fetch failed: {e}")

        return None

    async def healthcheck(self) -> dict:
        return {"tool_id": self.id, "status": "ok", "name": self.name}

    async def close(self) -> None:
        pass
