"""FAR threshold checker — MPT, SAT, TINA, and other key thresholds."""

import time
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from .base import BaseTool, ToolRunResult, Citation


class ThresholdInfo(BaseModel):
    name: str
    value: int
    far_reference: str
    description: str
    requirements: list[str]


class ThresholdCheckOutput(BaseModel):
    thresholds: list[ThresholdInfo]
    applicable: list[ThresholdInfo]
    contract_value: Optional[int]
    summary: str


# Current FAR thresholds (2024 - update annually)
FAR_THRESHOLDS = {
    "micro_purchase": ThresholdInfo(
        name="Micro-Purchase Threshold (MPT)",
        value=10000,
        far_reference="FAR 2.101, 13.201",
        description="Purchases at or below this threshold may be made without obtaining competitive quotations.",
        requirements=[
            "No competition required",
            "No written solicitation required",
            "Government purchase card acceptable",
            "No set-aside requirements (but best efforts for small business)",
        ],
    ),
    "simplified_acquisition": ThresholdInfo(
        name="Simplified Acquisition Threshold (SAT)",
        value=250000,
        far_reference="FAR 2.101, 13.000",
        description="Below SAT, simplified acquisition procedures apply. Most purchases use SF-18/SF-1449.",
        requirements=[
            "Simplified acquisition procedures apply (FAR Part 13)",
            "Full and open competition required unless set-aside",
            "No TINA/certified cost or pricing data required",
            "No CAS (Cost Accounting Standards) coverage",
            "Written solicitation typically required",
        ],
    ),
    "tina": ThresholdInfo(
        name="Truth in Negotiations Act (TINA) Threshold",
        value=2000000,
        far_reference="FAR 15.403-4, 41 U.S.C. 3501",
        description="Certified cost or pricing data required for contracts, modifications, and subcontracts exceeding this threshold (unless exception applies).",
        requirements=[
            "Certified cost or pricing data required",
            "Certificate of Current Cost or Pricing Data (DD Form 1861) required",
            "Exceptions: commercial items, adequate price competition, prices set by law",
            "Applies to prime and subcontracts",
        ],
    ),
    "ssa_review": ThresholdInfo(
        name="Source Selection Authority Review",
        value=10000000,
        far_reference="FAR 15.303",
        description="Contracts above this level typically require senior SSA designation and enhanced competition.",
        requirements=[
            "Senior official designated as Source Selection Authority",
            "Source Selection Advisory Council (SSAC) typically required",
            "Enhanced best value documentation",
            "Independent cost estimate required",
        ],
    ),
    "cas": ThresholdInfo(
        name="Cost Accounting Standards (CAS) Threshold",
        value=2000000,
        far_reference="FAR 30.201, 48 CFR 9903.201-1",
        description="CAS coverage required for negotiated defense contracts above this threshold.",
        requirements=[
            "CAS disclosure statement required",
            "Compliance with CAS 9900-9999",
            "Exceptions: small business, firm-fixed-price commercial items",
            "Full CAS coverage at $50M (or modified at $2M)",
        ],
    ),
    "subcontracting_plan": ThresholdInfo(
        name="Small Business Subcontracting Plan Threshold",
        value=750000,
        far_reference="FAR 19.702, 52.219-9",
        description="Other than small businesses must submit subcontracting plans for contracts exceeding this threshold.",
        requirements=[
            "Small business subcontracting plan required (FAR 52.219-9)",
            "Applies to large business prime contractors only",
            "Goals for: SB, SDB, WOSB, HUBZone, VOSB, SDVOSB",
            "Construction/A-E threshold: $1.5M",
        ],
    ),
    "eeo": ThresholdInfo(
        name="Equal Opportunity Threshold",
        value=10000,
        far_reference="FAR 22.802, 52.222-26",
        description="EEO requirements (Executive Order 11246) apply to contracts exceeding this threshold.",
        requirements=[
            "Equal Opportunity clause (52.222-26) required",
            "Prohibition of segregated facilities (52.222-21) required",
            "Affirmative Action requirements at $50K+",
            "Written AAP required for 50+ employees and $50K+ contracts",
        ],
    ),
    "veterans": ThresholdInfo(
        name="Veterans Employment Threshold",
        value=150000,
        far_reference="FAR 22.1302, 52.222-35",
        description="Affirmative action for veterans required for contracts exceeding this threshold.",
        requirements=[
            "52.222-35 Equal Opportunity for Veterans required",
            "52.222-37 Employment Reports on Veterans required",
            "VETS-4212 report required annually (100+ employees)",
        ],
    ),
}


class ThresholdCheckerTool(BaseTool):
    """Check applicable FAR thresholds for a given contract value."""

    id = "threshold.check"
    name = "FAR Threshold Checker"
    description = "Look up applicable FAR thresholds (MPT, SAT, TINA, CAS, etc.) for a contract value."
    input_schema = {
        "type": "object",
        "properties": {
            "contract_value": {"type": "integer", "description": "Estimated contract value in dollars"},
            "threshold_name": {"type": "string", "description": "Specific threshold to look up"},
        },
    }
    output_schema = {"type": "object"}

    async def run(self, params: dict) -> ToolRunResult:
        start = time.time()
        contract_value = params.get("contract_value")
        threshold_name = params.get("threshold_name", "").lower()

        try:
            all_thresholds = list(FAR_THRESHOLDS.values())

            if threshold_name:
                # Look up specific threshold
                matching = [t for t in all_thresholds if threshold_name in t.name.lower()]
                applicable = matching or all_thresholds
            elif contract_value is not None:
                # Find all thresholds that apply to this value
                applicable = [t for t in all_thresholds if t.value <= contract_value]
                applicable.sort(key=lambda t: t.value)
            else:
                applicable = all_thresholds

            if contract_value is not None:
                if contract_value <= 10000:
                    summary = f"${contract_value:,} is at or below the Micro-Purchase Threshold ($10K) — simplified purchase, no competition required."
                elif contract_value <= 250000:
                    summary = f"${contract_value:,} is above MPT but below SAT ($250K) — simplified acquisition procedures apply."
                elif contract_value <= 2000000:
                    summary = f"${contract_value:,} is above SAT but below TINA threshold ($2M) — standard negotiated procurement, no certified cost data required."
                elif contract_value <= 10000000:
                    summary = f"${contract_value:,} is above TINA threshold ($2M) — certified cost or pricing data required unless exception applies."
                else:
                    summary = f"${contract_value:,} is a major acquisition — TINA, CAS, SSA review, and enhanced competition requirements apply."
            else:
                summary = f"Showing {len(applicable)} threshold(s)"

            output = ThresholdCheckOutput(
                thresholds=all_thresholds,
                applicable=applicable,
                contract_value=contract_value,
                summary=summary,
            )

            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=output.model_dump(),
                citations=[
                    Citation(
                        source_name="Federal Acquisition Regulation",
                        source_url="https://www.acquisition.gov/far/2.101",
                        source_label="FAR 2.101 — Definitions",
                        retrieved_at=datetime.utcnow(),
                        snippet=summary,
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
