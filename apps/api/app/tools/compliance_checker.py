"""FAR Compliance Checker — validates solicitation clauses against FAR requirements."""

import time
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
import structlog

from .base import BaseTool, ToolRunResult, Citation
from .document_parse import FAR_CLAUSE_TITLES

logger = structlog.get_logger(__name__)


class ComplianceIssue(BaseModel):
    severity: str  # "error", "warning", "info"
    category: str  # "missing_required", "set_aside", "commercial", "cybersecurity", etc.
    clause_number: Optional[str] = None
    description: str
    recommendation: str
    far_reference: Optional[str] = None  # e.g. "FAR 52.219-6"


class ComplianceReport(BaseModel):
    score: int = Field(ge=0, le=100)  # 0-100
    grade: str  # A, B, C, D, F
    clauses_found: list[str]
    issues: list[ComplianceIssue]
    required_missing: list[str]
    recommended_missing: list[str]
    contract_type_detected: Optional[str] = None
    set_aside_detected: Optional[str] = None
    value_threshold_detected: Optional[str] = None
    summary: str


# Required clauses for commercial item acquisitions (FAR Part 12)
COMMERCIAL_REQUIRED = [
    "52.212-1",  # Instructions to Offerors
    "52.212-4",  # Contract Terms and Conditions—Commercial
    "52.212-5",  # Statutory Requirements
]

# Required for EVERY federal solicitation
ALWAYS_REQUIRED = [
    "52.204-7",   # SAM registration
    "52.233-1",   # Disputes
    "52.232-33",  # Payment by EFT
    "52.252-1",   # Solicitation Provisions Incorporated by Reference
    "52.252-2",   # Clauses Incorporated by Reference
]

# Required for small business set-asides
SMALL_BUSINESS_REQUIRED = [
    "52.219-1",   # Small Business Program Representations
    "52.219-6",   # Notice of Total Small Business Set-Aside (for SB set-asides)
    "52.219-8",   # Utilization of Small Business Concerns
]

# Required for DoD contracts
DOD_CYBERSECURITY_REQUIRED = [
    "252.204-7012",  # Safeguarding Covered Defense Information
    "252.204-7019",  # NIST SP 800-171 Assessment Requirements
    "252.204-7020",  # NIST SP 800-171 DoD Assessment Requirements
]

# Equal opportunity (required for contracts > $10K)
EEO_REQUIRED = [
    "52.222-21",   # Prohibition of Segregated Facilities
    "52.222-26",   # Equal Opportunity
]

# SAM clause indicators
SET_ASIDE_INDICATORS = {
    "52.219-6": "Total Small Business",
    "52.219-4": "HUBZone",
    "52.219-14": "Small Business (Limitations on Subcontracting)",
}


class ComplianceCheckerTool(BaseTool):
    """Check solicitation documents for FAR compliance issues."""

    id = "compliance.check_solicitation"
    name = "FAR Compliance Checker"
    description = (
        "Analyze a solicitation's clauses against FAR/DFARS requirements. "
        "Returns a compliance score, missing required clauses, and recommendations."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "clauses_found": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of clause numbers found in document",
            },
            "full_text": {
                "type": "string",
                "description": "Full document text for context analysis",
            },
            "contract_type": {
                "type": "string",
                "description": "Detected contract type (commercial, services, etc.)",
            },
        },
        "required": ["clauses_found"],
    }
    output_schema = {"type": "object"}

    async def run(self, params: dict) -> ToolRunResult:
        start = time.time()

        clauses_found = set(params.get("clauses_found", []))
        full_text = params.get("full_text", "").lower()
        contract_type = params.get("contract_type", "")

        try:
            # Detect context from text
            is_commercial = (
                "commercial item" in full_text or
                "commercial product" in full_text or
                any(c in clauses_found for c in ["52.212-1", "52.212-4", "52.212-5"])
            )
            is_dod = (
                "department of defense" in full_text or
                "dod" in full_text or
                any(c.startswith("252.") for c in clauses_found)
            )
            is_small_business = (
                "small business set-aside" in full_text or
                "total small business" in full_text or
                "52.219-6" in clauses_found
            )

            # Determine set-aside
            set_aside = None
            for clause, label in SET_ASIDE_INDICATORS.items():
                if clause in clauses_found:
                    set_aside = label
                    break

            # Detect value threshold
            value_threshold = None
            if "micro-purchase" in full_text:
                value_threshold = "Micro-Purchase (<$10K)"
            elif "simplified acquisition" in full_text or "sat" in full_text:
                value_threshold = "Simplified Acquisition ($10K-$250K)"
            elif "large business" in full_text or "full and open" in full_text:
                value_threshold = "Above SAT (>$250K)"

            issues: list[ComplianceIssue] = []

            # Check always-required clauses
            for clause in ALWAYS_REQUIRED:
                if clause not in clauses_found:
                    issues.append(ComplianceIssue(
                        severity="error",
                        category="missing_required",
                        clause_number=clause,
                        description=f"Required clause {clause} ({FAR_CLAUSE_TITLES.get(clause, 'Unknown')}) is missing",
                        recommendation=f"Add {clause} to the solicitation",
                        far_reference=f"FAR {clause}",
                    ))

            # Check commercial item requirements
            if is_commercial:
                for clause in COMMERCIAL_REQUIRED:
                    if clause not in clauses_found:
                        issues.append(ComplianceIssue(
                            severity="error",
                            category="commercial",
                            clause_number=clause,
                            description=f"Commercial item acquisition requires {clause} ({FAR_CLAUSE_TITLES.get(clause, '')})",
                            recommendation=f"Add {clause} per FAR Part 12 requirements",
                            far_reference="FAR 12.301",
                        ))

            # Check small business requirements
            if is_small_business:
                for clause in SMALL_BUSINESS_REQUIRED:
                    if clause not in clauses_found:
                        issues.append(ComplianceIssue(
                            severity="warning",
                            category="set_aside",
                            clause_number=clause,
                            description=f"Small business set-aside may require {clause}",
                            recommendation=f"Verify whether {clause} is required for this set-aside type",
                            far_reference="FAR 19.507",
                        ))

            # Check DoD cybersecurity requirements
            if is_dod:
                for clause in DOD_CYBERSECURITY_REQUIRED:
                    if clause not in clauses_found:
                        issues.append(ComplianceIssue(
                            severity="warning",
                            category="cybersecurity",
                            clause_number=clause,
                            description=f"DoD contract may require DFARS {clause} ({FAR_CLAUSE_TITLES.get(clause, '')})",
                            recommendation="Review DFARS 204.7300 for cybersecurity clause requirements",
                            far_reference=f"DFARS {clause}",
                        ))

            # Check EEO requirements
            for clause in EEO_REQUIRED:
                if clause not in clauses_found:
                    issues.append(ComplianceIssue(
                        severity="warning",
                        category="equal_opportunity",
                        clause_number=clause,
                        description=f"EEO clause {clause} ({FAR_CLAUSE_TITLES.get(clause, '')}) not found",
                        recommendation=f"Add {clause} if contract exceeds $10,000",
                        far_reference="FAR 22.810",
                    ))

            # Check for 52.203-12 if large contract suspected
            if value_threshold and "Above SAT" in (value_threshold or ""):
                if "52.203-12" not in clauses_found:
                    issues.append(ComplianceIssue(
                        severity="warning",
                        category="ethics",
                        clause_number="52.203-12",
                        description="Limitation on Payments to Influence may be required for contracts >$150K",
                        recommendation="Add 52.203-12 if contract exceeds $150,000 threshold",
                        far_reference="FAR 3.808",
                    ))

            # Calculate score
            errors = sum(1 for i in issues if i.severity == "error")
            warnings = sum(1 for i in issues if i.severity == "warning")

            base_score = 100
            base_score -= errors * 15
            base_score -= warnings * 5
            score = max(0, min(100, base_score))

            if score >= 90:
                grade = "A"
            elif score >= 80:
                grade = "B"
            elif score >= 70:
                grade = "C"
            elif score >= 60:
                grade = "D"
            else:
                grade = "F"

            required_missing = [i.clause_number for i in issues if i.severity == "error" and i.clause_number]
            recommended_missing = [i.clause_number for i in issues if i.severity == "warning" and i.clause_number]

            # Summary
            if score >= 90:
                summary = f"Good compliance ({len(issues)} minor items to review)"
            elif score >= 70:
                summary = f"Acceptable compliance with {errors} required issues and {warnings} recommendations"
            else:
                summary = f"Compliance concerns: {errors} required clauses missing, {warnings} recommendations"

            report = ComplianceReport(
                score=score,
                grade=grade,
                clauses_found=list(clauses_found),
                issues=issues,
                required_missing=required_missing,
                recommended_missing=recommended_missing,
                contract_type_detected="Commercial Item" if is_commercial else ("DoD" if is_dod else "Standard"),
                set_aside_detected=set_aside,
                value_threshold_detected=value_threshold,
                summary=summary,
            )

            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=report.model_dump(),
                citations=[
                    Citation(
                        source_name="Federal Acquisition Regulation",
                        source_url="https://www.acquisition.gov/far",
                        source_label="FAR — Federal Acquisition Regulation",
                        retrieved_at=datetime.utcnow(),
                        snippet=f"Compliance score: {score}/100 (Grade {grade})",
                    )
                ],
                duration_ms=(time.time() - start) * 1000,
                status="success",
            )

        except Exception as e:
            logger.error("compliance_check_error", error=str(e))
            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=None,
                citations=[],
                duration_ms=(time.time() - start) * 1000,
                status="error",
                error_message=str(e),
            )

    def build_citations(self, params: dict, output) -> list:
        return []

    async def healthcheck(self) -> dict:
        return {"tool_id": self.id, "status": "healthy", "message": f"{self.name} is operational"}

    async def close(self) -> None:
        pass
