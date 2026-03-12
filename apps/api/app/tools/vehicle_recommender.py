"""Contract vehicle recommender — GWAC, IDIQ, BPA, GSA Schedule recommendation."""

import time
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import BaseTool, ToolRunResult, Citation


class VehicleRecommendation(BaseModel):
    vehicle_name: str
    vehicle_type: str  # GWAC, IDIQ, BPA, GSA Schedule, Open Market
    contract_number: Optional[str] = None
    managing_agency: str
    description: str
    best_for: list[str]
    naics_codes: list[str]
    max_value: Optional[str] = None
    ceiling: Optional[str] = None
    small_business_options: bool
    set_aside_available: bool
    url: str
    pros: list[str]
    cons: list[str]


class VehicleOutput(BaseModel):
    recommendations: list[VehicleRecommendation]
    reasoning: str
    requirement_summary: str
    procurement_approach: str


# Acquisition vehicle knowledge base
VEHICLES = [
    VehicleRecommendation(
        vehicle_name="OASIS+",
        vehicle_type="GWAC",
        contract_number="47QRAA23D0001",
        managing_agency="GSA",
        description="One Acquisition Solution for Integrated Services Plus — professional and management support services",
        best_for=["Management consulting", "Program management", "IT services", "Professional services"],
        naics_codes=["541", "561", "611"],
        ceiling="$60 Billion",
        small_business_options=True,
        set_aside_available=True,
        url="https://www.gsa.gov/oasis",
        pros=["Broad scope", "Pre-competed vendors", "SB set-aside pools", "No ceiling per task order"],
        cons=["Complex to use", "Requires delegation of procurement authority"],
    ),
    VehicleRecommendation(
        vehicle_name="8(a) STARS III",
        vehicle_type="GWAC",
        contract_number="47QTCB20D0001",
        managing_agency="GSA",
        description="Streamlined Technology Acquisition Resource for Services III — IT services via 8(a) small businesses",
        best_for=["IT services", "Cybersecurity", "Cloud services", "8(a) small business requirements"],
        naics_codes=["541511", "541512", "541513", "541519"],
        ceiling="$50 Billion",
        small_business_options=True,
        set_aside_available=True,
        url="https://www.gsa.gov/8astars3",
        pros=["8(a) sole-source up to $25M", "IT-focused", "Pre-vetted vendors", "Fast ordering"],
        cons=["IT only", "8(a) firms only"],
    ),
    VehicleRecommendation(
        vehicle_name="Alliant 3",
        vehicle_type="GWAC",
        managing_agency="GSA",
        description="Large-business GWAC for complex IT services and enterprise IT solutions",
        best_for=["Enterprise IT", "Cloud migration", "AI/ML services", "Large IT programs"],
        naics_codes=["541511", "541512", "541519"],
        ceiling="$75 Billion",
        small_business_options=False,
        set_aside_available=False,
        url="https://www.gsa.gov/alliant3",
        pros=["Largest IT GWAC ceiling", "Complex IT solutions", "Enterprise-grade vendors"],
        cons=["Large business only", "Currently in solicitation phase"],
    ),
    VehicleRecommendation(
        vehicle_name="SEWP V",
        vehicle_type="GWAC",
        contract_number="NNG15SC03B",
        managing_agency="NASA",
        description="Solutions for Enterprise-Wide Procurement V — IT products and services",
        best_for=["IT hardware/software", "Cloud services", "Cybersecurity products", "AV equipment"],
        naics_codes=["334", "541511", "541519"],
        ceiling="$20 Billion",
        small_business_options=True,
        set_aside_available=True,
        url="https://www.sewp.nasa.gov",
        pros=["Fast ordering (24-48 hours for products)", "Strong for products+services", "Large vendor pool"],
        cons=["IT focused only", "Not ideal for labor-dominant services"],
    ),
    VehicleRecommendation(
        vehicle_name="GSA MAS (Federal Supply Schedule)",
        vehicle_type="GSA Schedule",
        managing_agency="GSA",
        description="Multiple Award Schedule — thousands of commercial vendors pre-negotiated by GSA",
        best_for=["Commercial products", "Professional services", "IT", "Office supplies", "Furniture"],
        naics_codes=["All NAICS"],
        ceiling="No program ceiling",
        small_business_options=True,
        set_aside_available=True,
        url="https://www.gsa.gov/schedules",
        pros=["Broad scope", "Fastest path for commercial items", "FAR Part 8 ordering", "Any agency can use"],
        cons=["Not for highly complex custom development", "Pricing can vary by vendor"],
    ),
    VehicleRecommendation(
        vehicle_name="CIOSP4",
        vehicle_type="GWAC",
        managing_agency="NIH",
        description="Chief Information Officer — Solutions and Partners 4 for IT services",
        best_for=["IT services", "Health IT", "Cybersecurity", "AI/ML"],
        naics_codes=["541511", "541512", "541519", "541715"],
        ceiling="$60 Billion",
        small_business_options=True,
        set_aside_available=True,
        url="https://nitaac.nih.gov/ciosp4",
        pros=["Health IT expertise", "SB set-aside available", "No fee to agencies"],
        cons=["IT focused", "Must use NITAAC ordering portal"],
    ),
    VehicleRecommendation(
        vehicle_name="Open Market (FAR Part 15)",
        vehicle_type="Open Market",
        managing_agency="Agency",
        description="Traditional competitive acquisition — full and open competition with agency as contracting officer",
        best_for=["Unique requirements", "No suitable vehicle exists", "High-value complex requirements"],
        naics_codes=["All NAICS"],
        ceiling=None,
        small_business_options=True,
        set_aside_available=True,
        url="https://www.acquisition.gov/far/part-15",
        pros=["Full flexibility", "Any requirement type", "No vehicle fee or delegation needed"],
        cons=["Slowest method", "Highest acquisition burden", "Must do market research, sources sought, full RFP"],
    ),
]


class VehicleRecommenderTool(BaseTool):
    """Recommend appropriate contract vehicles based on requirement characteristics."""

    id = "vehicle.recommend"
    name = "Contract Vehicle Recommender"
    description = "Recommend the best GWAC, IDIQ, GSA Schedule, or open market approach for a requirement."
    input_schema = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "What you're buying"},
            "naics_code": {"type": "string"},
            "estimated_value": {"type": "integer"},
            "small_business": {"type": "boolean", "description": "Prefer small business"},
            "dod": {"type": "boolean", "description": "DoD agency"},
        },
    }
    output_schema = {"type": "object"}

    async def run(self, params: dict) -> ToolRunResult:
        start = time.time()
        description = params.get("description", "").lower()
        naics = params.get("naics_code", "")
        value = params.get("estimated_value", 0)
        prefer_sb = params.get("small_business", False)
        is_dod = params.get("dod", False)

        try:
            # Score vehicles
            scored = []
            for v in VEHICLES:
                score = 0

                # NAICS match
                if naics:
                    for v_naics in v.naics_codes:
                        if naics.startswith(v_naics) or v_naics == "All NAICS":
                            score += 30
                            break

                # Keyword match in description
                for keyword in v.best_for:
                    if keyword.lower() in description:
                        score += 20

                # Small business preference
                if prefer_sb and v.small_business_options:
                    score += 15

                # Value fit (open market better for >$100M, vehicles better for smaller)
                if value and value < 100_000_000 and v.vehicle_type != "Open Market":
                    score += 10
                elif value and value >= 100_000_000:
                    score += 5

                # IT keywords
                is_it = any(kw in description for kw in ["it ", "software", "cloud", "cyber", "data", "technology"])
                if is_it and "IT" in str(v.best_for):
                    score += 20

                scored.append((score, v))

            scored.sort(key=lambda x: x[0], reverse=True)
            recommendations = [v for _, v in scored[:3]]  # Top 3

            approach = (
                "Use an existing contract vehicle (faster, lower burden)"
                if recommendations[0].vehicle_type != "Open Market"
                else "Open market competition required"
            )

            output = VehicleOutput(
                recommendations=recommendations,
                reasoning=f"Matched based on: description keywords, NAICS {naics or 'not specified'}, value ${value:,}",
                requirement_summary=description[:200] if description else "Not specified",
                procurement_approach=approach,
            )

            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=output.model_dump(),
                citations=[
                    Citation(
                        source_name="GSA Acquisition Gateway",
                        source_url="https://hallways.cap.gsa.gov",
                        source_label="GSA Acquisition Gateway — Contract Vehicles",
                        retrieved_at=datetime.utcnow(),
                        snippet=f"Top recommendation: {recommendations[0].vehicle_name}",
                    )
                ],
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

    async def healthcheck(self) -> dict:
        return {"tool_id": self.id, "status": "ok", "name": self.name}

    async def close(self) -> None:
        pass
