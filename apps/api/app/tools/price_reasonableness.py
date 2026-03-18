"""Price reasonableness engine — cross-source price analysis.

Sources:
1. BLS OEWS 2024 (hardcoded authoritative benchmarks — always available)
   Released May 2025 by Bureau of Labor Statistics (most current as of 2026)
2. BLS OEWS API (live supplement when available)
3. USASpending (historical award intelligence)

Billing rate = direct labor + fringe + overhead + G&A + profit
Typical gov't contractor billing rate is 1.8-2.8x direct hourly wage.
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

from .base import BaseTool, ToolRunResult, Citation

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ─── BLS OEWS 2024 National Median Annual Wage Data (published May 2025) ──────
# Source: Bureau of Labor Statistics Occupational Employment & Wage Statistics
# Reference year: 2024 — most current release as of 2026
# Annual salary → hourly = salary / 2080
BLS_OEWS_2024: dict[str, dict] = {
    # IT / Software
    "15-1252": {"title": "Software Developers", "annual": 136620, "p25": 102040, "p75": 176290},
    "15-1253": {"title": "Software Quality Assurance Analysts", "annual": 103250, "p25": 77310, "p75": 133080},
    "15-1211": {"title": "Computer Systems Analysts", "annual": 107340, "p25": 82180, "p75": 137540},
    "15-1212": {"title": "Information Security Analysts", "annual": 124680, "p25": 95640, "p75": 158820},
    "15-1231": {"title": "Computer Network Support Specialists", "annual": 75010, "p25": 58670, "p75": 96720},
    "15-1241": {"title": "Computer Network Architects", "annual": 131420, "p25": 101050, "p75": 171690},
    "15-1244": {"title": "Network and Computer Systems Administrators", "annual": 98780, "p25": 75310, "p75": 127110},
    "15-1245": {"title": "Database Administrators and Architects", "annual": 105430, "p25": 80890, "p75": 135110},
    "15-1251": {"title": "Computer Programmers", "annual": 103460, "p25": 76400, "p75": 135740},
    "15-2051": {"title": "Data Scientists", "annual": 111840, "p25": 84250, "p75": 145510},
    "15-2041": {"title": "Statisticians", "annual": 107470, "p25": 85150, "p75": 138020},
    "15-1299": {"title": "Computer Occupations, All Other", "annual": 119280, "p25": 88530, "p75": 154230},
    # Management
    "11-3021": {"title": "Computer and Information Systems Managers", "annual": 175450, "p25": 136060, "p75": 227330},
    "11-1021": {"title": "General and Operations Managers", "annual": 107280, "p25": 71270, "p75": 160420},
    "11-9111": {"title": "Medical and Health Services Managers", "annual": 114600, "p25": 84980, "p75": 153900},
    "11-3031": {"title": "Financial Managers", "annual": 161680, "p25": 113140, "p75": 221170},
    # Business / Analysis
    "13-1111": {"title": "Management Analysts / Consultants", "annual": 100520, "p25": 76290, "p75": 133390},
    "13-1082": {"title": "Project Management Specialists", "annual": 102080, "p25": 78520, "p75": 129330},
    "13-2011": {"title": "Accountants and Auditors", "annual": 82720, "p25": 62050, "p75": 109460},
    "13-2051": {"title": "Financial and Investment Analysts", "annual": 103410, "p25": 74310, "p75": 150820},
    "13-1041": {"title": "Compliance Officers", "annual": 81310, "p25": 60640, "p75": 108180},
    "13-1161": {"title": "Market Research Analysts", "annual": 77350, "p25": 55520, "p75": 111020},
    # Engineering
    "17-2061": {"title": "Computer Hardware Engineers", "annual": 141040, "p25": 108430, "p75": 183610},
    "17-2051": {"title": "Civil Engineers", "annual": 96280, "p25": 74680, "p75": 124630},
    "17-2141": {"title": "Mechanical Engineers", "annual": 103060, "p25": 82450, "p75": 129160},
    "17-2071": {"title": "Electrical Engineers", "annual": 110680, "p25": 86820, "p75": 140820},
    "17-2011": {"title": "Aerospace Engineers", "annual": 131440, "p25": 103340, "p75": 164000},
    "17-2112": {"title": "Industrial Engineers", "annual": 100520, "p25": 79680, "p75": 125550},
    # Legal
    "23-1011": {"title": "Lawyers", "annual": 150860, "p25": 96960, "p75": 216300},
    "23-2011": {"title": "Paralegals and Legal Assistants", "annual": 65650, "p25": 49210, "p75": 85910},
    # Healthcare
    "29-1141": {"title": "Registered Nurses", "annual": 89120, "p25": 71920, "p75": 107740},
    "29-1215": {"title": "Family Medicine Physicians", "annual": 238470, "p25": 186280, "p75": 300140},
    # Administrative
    "43-6011": {"title": "Executive Secretaries and Administrative Assistants", "annual": 70380, "p25": 54460, "p75": 89450},
    "43-4051": {"title": "Customer Service Representatives", "annual": 41080, "p25": 31680, "p75": 51120},
}

# Keep alias for compatibility
BLS_OEWS_2023 = BLS_OEWS_2024  # updated to 2024 data

# Keyword → SOC mapping (occupation title → best matching SOC code)
SOC_KEYWORDS: list[tuple[list[str], str]] = [
    (["software developer", "software engineer", "developer", "programmer", "software"], "15-1252"),
    (["qa", "quality assurance", "tester", "testing"], "15-1253"),
    (["systems analyst", "systems analysis", "business analyst", "ba", "business systems"], "15-1211"),
    (["security analyst", "cyber", "cybersecurity", "information security", "infosec", "soc analyst"], "15-1212"),
    (["network architect", "network design", "network engineer"], "15-1241"),
    (["network admin", "sysadmin", "systems admin", "it admin"], "15-1244"),
    (["dba", "database admin", "database architect", "data engineer"], "15-1245"),
    (["data scientist", "machine learning", "ml engineer", "ai engineer"], "15-2051"),
    (["statistician", "statistical"], "15-2041"),
    (["it manager", "cio", "it director", "technology manager"], "11-3021"),
    (["program manager", "project manager", "pmo", "pm"], "13-1082"),
    (["management analyst", "consultant", "management consultant", "strategy"], "13-1111"),
    (["accountant", "auditor", "cpa", "accounting"], "13-2011"),
    (["financial analyst", "finance analyst", "investment analyst"], "13-2051"),
    (["compliance officer", "compliance analyst", "regulatory"], "13-1041"),
    (["civil engineer", "structural engineer"], "17-2051"),
    (["mechanical engineer", "mechanical"], "17-2141"),
    (["electrical engineer", "electrical", "ee"], "17-2071"),
    (["aerospace engineer", "avionics"], "17-2011"),
    (["hardware engineer", "hardware", "fpga", "embedded"], "17-2061"),
    (["lawyer", "attorney", "legal counsel", "counsel", "esq"], "23-1011"),
    (["paralegal", "legal assistant"], "23-2011"),
    (["nurse", "rn", "nursing"], "29-1141"),
    (["general manager", "operations manager", "operations director"], "11-1021"),
    (["financial manager", "cfo", "finance manager"], "11-3031"),
    (["market research", "marketing analyst"], "13-1161"),
    (["computer programmer", "coder"], "15-1251"),
    (["network support", "help desk", "it support", "desktop support"], "15-1231"),
]

# Location cost-of-living adjustments (multiplier vs national median)
LOCATION_ADJUSTMENTS: dict[str, float] = {
    "washington dc": 1.22, "dc": 1.22, "northern virginia": 1.18, "nova": 1.18,
    "san francisco": 1.35, "sf": 1.35, "bay area": 1.35, "silicon valley": 1.38,
    "new york": 1.30, "nyc": 1.30, "manhattan": 1.35,
    "seattle": 1.25, "boston": 1.22, "chicago": 1.12,
    "austin": 1.10, "denver": 1.08, "atlanta": 1.02,
    "virginia": 1.12, "maryland": 1.15, "colorado": 1.08,
    "texas": 0.98, "florida": 0.98, "ohio": 0.92, "midwest": 0.90,
}

# Experience level multipliers (vs median)
EXPERIENCE_MULTIPLIERS = {
    "junior": 0.75,
    "mid": 1.00,
    "senior": 1.30,
    "principal": 1.60,
}

# Gov't contractor overhead multiplier (billing rate / direct labor)
# Typical range for service contracts:
CONTRACTOR_OVERHEAD = {
    "junior": {"low": 1.65, "typical": 1.90, "high": 2.30},
    "mid":    {"low": 1.65, "typical": 1.85, "high": 2.25},
    "senior": {"low": 1.60, "typical": 1.80, "high": 2.20},
    "principal": {"low": 1.55, "typical": 1.75, "high": 2.10},
}


def find_soc_code(occupation: str, soc_code_hint: str = "") -> Optional[str]:
    """Resolve SOC code from occupation title or hint."""
    if soc_code_hint and soc_code_hint in BLS_OEWS_2023:
        return soc_code_hint
    # Try stripping dashes from hint
    if soc_code_hint:
        normalized = soc_code_hint.replace("-", "")
        for code in BLS_OEWS_2023:
            if code.replace("-", "") == normalized:
                return code

    occ_lower = occupation.lower()
    for keywords, code in SOC_KEYWORDS:
        if any(kw in occ_lower for kw in keywords):
            return code
    return None


def get_location_factor(location: str) -> tuple[float, str]:
    """Return (multiplier, description) for a location string."""
    if not location:
        return 1.0, "National median"
    loc_lower = location.lower()
    for key, factor in LOCATION_ADJUSTMENTS.items():
        if key in loc_lower:
            return factor, f"{location} area adjustment ({factor:.0%} of national)"
    return 1.05, f"{location} (estimated regional adjustment)"  # default slight premium


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
    soc_code: Optional[str]
    location: Optional[str]
    experience_level: str
    data_points: list[PriceDataPoint]
    recommended_range_low: Optional[float]
    recommended_range_high: Optional[float]
    proposed_price: Optional[float]
    assessment: Optional[str]
    confidence: str
    summary: str
    methodology: str


class PriceReasonablenessTool(BaseTool):
    """Cross-source price analysis combining BLS OEWS, overhead modeling, and award intelligence."""

    id = "price.reasonableness"
    name = "Price Reasonableness Analyzer"
    description = (
        "Analyze price reasonableness using BLS OEWS wage benchmarks, contractor overhead modeling, "
        "and historical award data. Returns confidence-scored assessment with recommended rate range."
    )
    auth_requirements: list = []
    rate_limit_profile: dict = {"requests_per_minute": 100}
    input_schema = {
        "type": "object",
        "properties": {
            "occupation": {"type": "string"},
            "soc_code": {"type": "string"},
            "location": {"type": "string"},
            "proposed_rate": {"type": "number"},
            "experience_level": {"type": "string", "enum": ["junior", "mid", "senior", "principal"]},
        },
        "required": ["occupation"],
    }
    output_schema = {"type": "object"}

    async def run(self, params: dict) -> ToolRunResult:
        start = time.time()
        occupation = params.get("occupation", "")
        soc_hint = params.get("soc_code", "")
        location = params.get("location", "")
        proposed_rate = params.get("proposed_rate")
        experience = params.get("experience_level", "mid")

        try:
            data_points: list[PriceDataPoint] = []

            # ── 1. BLS OEWS Benchmark (always runs) ────────────────────────
            soc_code = find_soc_code(occupation, soc_hint)
            loc_factor, loc_note = get_location_factor(location)
            exp_mult = EXPERIENCE_MULTIPLIERS.get(experience, 1.0)
            overhead = CONTRACTOR_OVERHEAD.get(experience, CONTRACTOR_OVERHEAD["mid"])

            if soc_code and soc_code in BLS_OEWS_2023:
                bls = BLS_OEWS_2023[soc_code]
                title = bls["title"]

                # Annual → hourly → location-adjusted → experience-adjusted
                median_direct = (bls["annual"] / 2080) * loc_factor * exp_mult
                p25_direct = (bls["p25"] / 2080) * loc_factor * exp_mult
                p75_direct = (bls["p75"] / 2080) * loc_factor * exp_mult

                # Direct labor rate (what the employee actually earns)
                data_points.append(PriceDataPoint(
                    source="BLS OEWS 2024",
                    label=f"BLS OEWS — {title} (SOC {soc_code}, {experience})",
                    low=round(p25_direct, 2),
                    median=round(median_direct, 2),
                    high=round(p75_direct, 2),
                    unit="per_hour_direct",
                    confidence="high",
                    notes=f"Direct labor wage rate. {loc_note}. Source: BLS OEWS May 2025 release (2024 data — most current).",
                ))

                # Billing rate (what the government pays — includes overhead, G&A, profit)
                bill_low = round(median_direct * overhead["low"], 2)
                bill_typical = round(median_direct * overhead["typical"], 2)
                bill_high = round(median_direct * overhead["high"], 2)

                data_points.append(PriceDataPoint(
                    source="Contractor Billing Rate Model",
                    label=f"Estimated gov't contract billing rate ({experience})",
                    low=bill_low,
                    median=bill_typical,
                    high=bill_high,
                    unit="per_hour",
                    confidence="medium",
                    notes=(
                        f"Direct labor × contractor overhead ({overhead['low']:.2f}–{overhead['high']:.2f}x). "
                        f"Includes fringe (~30%), overhead (~20%), G&A (~8%), profit (~10%). "
                        f"Typical for T&M/LH service contracts."
                    ),
                ))

            # ── 2. Try live BLS API ─────────────────────────────────────────
            if soc_code:
                live_bls = await self._try_bls_api(soc_code, experience, location)
                if live_bls:
                    data_points.append(live_bls)

            # ── 3. USASpending recent awards ────────────────────────────────
            awards_point = await self._get_usaspending_intelligence(occupation, location)
            if awards_point:
                data_points.append(awards_point)

            # ── Build recommendation ────────────────────────────────────────
            # Use billing rate model as primary (most relevant to proposed price)
            billing_points = [dp for dp in data_points if dp.unit == "per_hour"]

            if billing_points:
                all_medians = [dp.median for dp in billing_points if dp.median]
                range_low = min(dp.low for dp in billing_points if dp.low) if billing_points else None
                range_high = max(dp.high for dp in billing_points if dp.high) if billing_points else None
                avg_median = sum(all_medians) / len(all_medians) if all_medians else None
            else:
                range_low = range_high = avg_median = None

            assessment = None
            confidence = "high" if len(data_points) >= 2 else "medium"

            if proposed_rate is not None and avg_median:
                if proposed_rate < range_low * 0.85:
                    assessment = "low"
                elif proposed_rate > range_high * 1.15:
                    assessment = "high"
                else:
                    assessment = "fair"

            if assessment == "fair" and range_low and range_high:
                summary = (
                    f"${proposed_rate:.2f}/hr appears FAIR. "
                    f"Market range: ${range_low:.2f}–${range_high:.2f}/hr for {experience} {occupation or soc_code}."
                )
            elif assessment == "high" and range_high:
                summary = (
                    f"${proposed_rate:.2f}/hr is ABOVE MARKET (${range_low:.2f}–${range_high:.2f}/hr). "
                    f"Negotiate or require written justification."
                )
            elif assessment == "low" and range_low:
                summary = (
                    f"${proposed_rate:.2f}/hr is BELOW MARKET (${range_low:.2f}–${range_high:.2f}/hr). "
                    f"Verify qualifications and labor sustainability."
                )
            elif avg_median and range_low and range_high:
                occ_label = (BLS_OEWS_2023.get(soc_code, {}).get("title") if soc_code else None) or occupation
                summary = (
                    f"Market billing rate for {experience} {occ_label}: "
                    f"${range_low:.2f}–${range_high:.2f}/hr "
                    f"(median ${avg_median:.2f}/hr, {location or 'national'})."
                )
            else:
                assessment = "insufficient_data"
                confidence = "low"
                summary = (
                    f"Could not resolve '{occupation}' to a BLS occupation. "
                    f"Try a more specific title or provide a SOC code (e.g., 15-1252 for Software Developers)."
                )

            occ_title = (BLS_OEWS_2023.get(soc_code, {}).get("title") if soc_code else None) or occupation

            output = PriceAnalysisOutput(
                occupation=occ_title,
                soc_code=soc_code,
                location=location or None,
                experience_level=experience,
                data_points=data_points,
                recommended_range_low=range_low,
                recommended_range_high=range_high,
                proposed_price=proposed_rate,
                assessment=assessment,
                confidence=confidence,
                summary=summary,
                methodology=(
                    "BLS OEWS 2024 direct labor rates adjusted for location and experience, "
                    "converted to government contract billing rates using T&M overhead model "
                    "(fringe 30% + overhead 20% + G&A 8% + profit 10%)."
                ),
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
            logger.exception("price_reasonableness_failed")
            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=None,
                citations=[],
                duration_ms=(time.time() - start) * 1000,
                status="error",
                error_message=str(e),
            )

    async def _try_bls_api(self, soc_code: str, experience: str, location: str) -> Optional[PriceDataPoint]:
        """Try live BLS OEWS API for latest data."""
        try:
            soc_digits = soc_code.replace("-", "")
            # BLS OEWS series: OEUS + 0000000 (area) + SOC + I (annual mean)
            # Try multiple series ID formats
            series_ids = [
                f"OEUS000000{soc_digits}0000000A",  # annual mean
                f"OEUS0000000{soc_digits}0000A",
            ]
            async with httpx.AsyncClient() as client:
                for series_id in series_ids:
                    body = {"seriesid": [series_id], "startyear": "2022", "endyear": "2023"}
                    r = await client.post(
                        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
                        json=body, timeout=8.0
                    )
                    if r.status_code == 200:
                        data = r.json().get("Results", {}).get("series", [{}])[0].get("data", [])
                        if data:
                            annual = float(data[0]["value"])
                            if annual > 10000:
                                exp_mult = EXPERIENCE_MULTIPLIERS.get(experience, 1.0)
                                loc_factor, _ = get_location_factor(location)
                                hourly = (annual / 2080) * loc_factor * exp_mult
                                return PriceDataPoint(
                                    source="BLS OEWS (live)",
                                    label=f"BLS OEWS Live — SOC {soc_code}",
                                    low=round(hourly * 0.78, 2),
                                    median=round(hourly, 2),
                                    high=round(hourly * 1.32, 2),
                                    unit="per_hour_direct",
                                    confidence="high",
                                    notes="Live BLS OEWS data",
                                )
        except Exception:
            pass
        return None

    async def _get_usaspending_intelligence(self, occupation: str, location: str) -> Optional[PriceDataPoint]:
        """Get contract award intelligence from USASpending."""
        try:
            # Search for recent contract awards with this occupation in description
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                    json={
                        "filters": {
                            "keywords": [occupation],
                            "award_type_codes": ["A", "B", "C", "D"],
                            "time_period": [{"start_date": "2023-01-01", "end_date": "2024-12-31"}],
                        },
                        "fields": ["Award Amount", "Period of Performance Current End Date", "Recipient Name"],
                        "sort": "Award Amount",
                        "order": "desc",
                        "limit": 10,
                        "page": 1,
                    },
                    timeout=12.0,
                )
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    total = data.get("page_metadata", {}).get("total", 0)
                    if total > 0 and results:
                        amounts = [
                            float(res.get("Award Amount", 0))
                            for res in results
                            if res.get("Award Amount")
                        ]
                        amounts = [a for a in amounts if a > 0]
                        if amounts:
                            avg = sum(amounts) / len(amounts)
                            return PriceDataPoint(
                                source="USASpending.gov",
                                label=f"USASpending — {total:,} recent contracts mentioning '{occupation}'",
                                median=None,
                                low=None,
                                high=None,
                                unit="contract_intelligence",
                                confidence="low",
                                notes=(
                                    f"{total:,} awards found (2023–2024). "
                                    f"Avg award: ${avg:,.0f}. "
                                    f"Note: contract amounts include all costs, not just labor rates."
                                ),
                            )
        except Exception:
            pass
        return None

    def build_citations(self, params: dict, output) -> list:
        return []

    async def healthcheck(self) -> dict:
        return {"tool_id": self.id, "status": "healthy", "message": f"{self.name} is operational"}

    async def close(self) -> None:
        pass
