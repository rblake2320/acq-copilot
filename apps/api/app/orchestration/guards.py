"""Guardrails for answer quality and compliance.

This module provides safety checks including source grounding verification,
calculation verification, PII detection, and disclaimer generation.
"""

import re
from typing import Optional
from pydantic import BaseModel


class GroundingIssue(BaseModel):
    """Issue with answer grounding in source data."""
    claim: str
    issue_type: str  # "unsupported", "contradicted", "speculative"
    severity: str  # "error", "warning", "info"
    suggested_fix: str


class CalculationMismatch(BaseModel):
    """Mismatch in calculations."""
    claimed_value: float
    raw_value: float
    difference: float
    percentage_error: float
    field_name: str


class PII_Detection(BaseModel):
    """Detected personally identifiable information."""
    pattern_type: str  # "ssn", "email", "phone", "credit_card", etc.
    value: str
    severity: str  # "high", "medium", "low"
    location: str


class SourceGroundingGuard:
    """Verifies that answer claims are grounded in tool outputs."""
    
    # Patterns indicating unsupported or speculative claims
    SPECULATIVE_PATTERNS = [
        r'\bmight\b',
        r'\bcould\b',
        r'\bprobably\b',
        r'\blikely\b',
        r'\bi\s+think\b',
        r'\bi\s+believe\b',
        r'\bapparently\b',
        r'\bseemingly\b',
        r'\bunfortunately\b',
    ]
    
    # Patterns for unsupported numerical claims
    NUMERICAL_PATTERNS = [
        r'\$[\d,]+(?:\.\d{2})?',
        r'\d+(?:,\d{3})*(?:\.\d{2})?',
        r'\d+%',
    ]

    @staticmethod
    def check(answer_text: str, tool_outputs: list[dict]) -> list[GroundingIssue]:
        """Check if answer is grounded in tool outputs.
        
        Args:
            answer_text: Generated answer text
            tool_outputs: List of tool result dicts
            
        Returns:
            List of GroundingIssue objects
        """
        issues = []
        
        # Extract numerical claims from answer
        answer_numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', answer_text)
        
        # Flatten output data to search through
        output_text = " ".join(str(item) for item in tool_outputs)
        
        # Check for unsupported numbers
        for number in answer_numbers:
            if number not in output_text:
                issues.append(GroundingIssue(
                    claim=number,
                    issue_type="unsupported",
                    severity="warning",
                    suggested_fix=f"Verify {number} is in tool outputs or remove claim"
                ))
        
        # Check for speculative language without attribution
        for pattern in SourceGroundingGuard.SPECULATIVE_PATTERNS:
            matches = re.finditer(pattern, answer_text, re.IGNORECASE)
            for match in matches:
                # Check if properly attributed
                context = answer_text[max(0, match.start()-50):match.end()+50]
                if not self._is_properly_attributed(context):
                    issues.append(GroundingIssue(
                        claim=match.group(),
                        issue_type="speculative",
                        severity="info",
                        suggested_fix="Strengthen with specific data or add caveat"
                    ))
        
        return issues

    @staticmethod
    def _is_properly_attributed(context: str) -> bool:
        """Check if claim is properly attributed to source.
        
        Args:
            context: Text around the claim
            
        Returns:
            True if attribution found
        """
        attribution_patterns = [
            r'(?:according to|from|based on)\s+',
            r'(?:USAspending|FAR|BLS|GSA)\b',
            r'data shows',
        ]
        
        return any(
            re.search(pattern, context, re.IGNORECASE)
            for pattern in attribution_patterns
        )


class CalculationVerificationGuard:
    """Verifies numerical calculations against source data."""
    
    @staticmethod
    def check(
        answer_text: str,
        raw_data: list[dict]
    ) -> list[CalculationMismatch]:
        """Verify calculations in answer against raw data.
        
        Args:
            answer_text: Answer with calculations
            raw_data: Raw data from tools
            
        Returns:
            List of CalculationMismatch objects
        """
        mismatches = []
        
        # Extract claimed calculations
        calculation_pattern = r'(\w+)\s+(?:is|equals|=)\s*([\d,]+(?:\.\d{2})?)'
        matches = re.finditer(calculation_pattern, answer_text)
        
        for match in matches:
            field_name = match.group(1)
            claimed_value = float(match.group(2).replace(",", ""))
            
            # Find corresponding value in raw data
            raw_value = CalculationVerificationGuard._find_value(
                field_name,
                raw_data
            )
            
            if raw_value is not None:
                error = abs(claimed_value - raw_value)
                if error > 0.01:  # More than $0.01 difference
                    pct_error = (error / raw_value * 100) if raw_value != 0 else 0
                    
                    if pct_error > 1:  # More than 1% error
                        mismatches.append(CalculationMismatch(
                            claimed_value=claimed_value,
                            raw_value=raw_value,
                            difference=error,
                            percentage_error=pct_error,
                            field_name=field_name
                        ))
        
        return mismatches

    @staticmethod
    def _find_value(field_name: str, data: list[dict]) -> Optional[float]:
        """Find field value in data.
        
        Args:
            field_name: Field name to find
            data: Data to search
            
        Returns:
            Float value or None
        """
        for item in data:
            if not isinstance(item, dict):
                continue
            
            for key, value in item.items():
                if key.lower() == field_name.lower():
                    try:
                        return float(str(value).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
        
        return None


class PIIDetectionGuard:
    """Detects personally identifiable information."""
    
    # PII patterns
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b(?:\+?1[-.\s]?)?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b'
    CREDIT_CARD_PATTERN = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    PASSPORT_PATTERN = r'\b[A-Z]{1,2}\d{6,9}\b'
    
    @staticmethod
    def detect(text: str) -> list[PII_Detection]:
        """Detect PII in text.
        
        Args:
            text: Text to scan
            
        Returns:
            List of detected PII
        """
        detections = []
        
        # Check SSN
        ssn_matches = re.finditer(PIIDetectionGuard.SSN_PATTERN, text)
        for match in ssn_matches:
            detections.append(PII_Detection(
                pattern_type="ssn",
                value=match.group(),
                severity="high",
                location=f"Position {match.start()}"
            ))
        
        # Check email
        email_matches = re.finditer(PIIDetectionGuard.EMAIL_PATTERN, text)
        for match in email_matches:
            # Personal email addresses are moderate concern
            if not PIIDetectionGuard._is_corporate_email(match.group()):
                detections.append(PII_Detection(
                    pattern_type="email",
                    value=match.group(),
                    severity="medium",
                    location=f"Position {match.start()}"
                ))
        
        # Check phone
        phone_matches = re.finditer(PIIDetectionGuard.PHONE_PATTERN, text)
        for match in phone_matches:
            detections.append(PII_Detection(
                pattern_type="phone",
                value=match.group(),
                severity="high",
                location=f"Position {match.start()}"
            ))
        
        # Check credit card
        cc_matches = re.finditer(PIIDetectionGuard.CREDIT_CARD_PATTERN, text)
        for match in cc_matches:
            detections.append(PII_Detection(
                pattern_type="credit_card",
                value=match.group(),
                severity="high",
                location=f"Position {match.start()}"
            ))
        
        return detections

    @staticmethod
    def _is_corporate_email(email: str) -> bool:
        """Check if email is corporate.
        
        Args:
            email: Email address
            
        Returns:
            True if corporate domain
        """
        corporate_domains = [
            "gsa.gov",
            "defense.gov",
            "state.gov",
            "treasury.gov",
            "hhs.gov",
            "usajobs.gov",
        ]
        
        domain = email.split("@")[1].lower()
        return any(domain.endswith(cd) for cd in corporate_domains)


class AcquisitionDisclaimerGuard:
    """Generates appropriate disclaimers for acquisition guidance."""
    
    STANDARD_DISCLAIMER = """
DISCLAIMER: This information is provided for reference purposes only and does not constitute 
legal advice. Users should consult with qualified legal counsel and acquisition professionals 
before making acquisition decisions. Regulations and rates are subject to change.
"""
    
    WAGE_DISCLAIMER = """
WAGE RATE DISCLAIMER: Wage data is based on the most recent Bureau of Labor Statistics data 
and prevailing wage determinations. Users should verify current rates with authoritative 
sources before making salary or compensation decisions.
"""
    
    PERDIEM_DISCLAIMER = """
PER DIEM DISCLAIMER: Per diem rates are current as of the query date and are subject to 
change without notice. Always verify rates with GSA or agency guidance before travel authorization.
"""
    
    REGULATION_DISCLAIMER = """
REGULATION DISCLAIMER: FAR and DFARS text provided is for reference only. Always consult 
the official regulation sources at acquisition.gov for the most current requirements. 
This information does not replace legal counsel.
"""
    
    SPENDING_DISCLAIMER = """
SPENDING DISCLAIMER: USAspending data is provided by the federal government but may have 
reporting delays or inaccuracies. Data should be verified against agency records for critical decisions.
"""

    @staticmethod
    def get_disclaimer(tool_ids: list[str]) -> str:
        """Get appropriate disclaimer(s) for tools used.
        
        Args:
            tool_ids: List of tool identifiers
            
        Returns:
            Relevant disclaimer text
        """
        disclaimers = [AcquisitionDisclaimerGuard.STANDARD_DISCLAIMER]
        
        if any("wage" in tid for tid in tool_ids):
            disclaimers.append(AcquisitionDisclaimerGuard.WAGE_DISCLAIMER)
        
        if any("perdiem" in tid for tid in tool_ids):
            disclaimers.append(AcquisitionDisclaimerGuard.PERDIEM_DISCLAIMER)
        
        if any("far" in tid or "regulation" in tid for tid in tool_ids):
            disclaimers.append(AcquisitionDisclaimerGuard.REGULATION_DISCLAIMER)
        
        if any("spending" in tid for tid in tool_ids):
            disclaimers.append(AcquisitionDisclaimerGuard.SPENDING_DISCLAIMER)
        
        return "\n".join(disclaimers)


class RateLimitGuard:
    """Rate limiting enforcement."""
    
    def __init__(self, limits: Optional[dict[str, int]] = None):
        """Initialize rate limiter.
        
        Args:
            limits: Dict of user_id -> max_requests_per_hour
        """
        self.limits = limits or {}
        self.usage: dict[str, list[float]] = {}

    async def check(self, user_id: str, tool_id: str) -> tuple[bool, str]:
        """Check if request is within rate limits.
        
        Args:
            user_id: User identifier
            tool_id: Tool being accessed
            
        Returns:
            Tuple of (allowed: bool, message: str)
        """
        if user_id not in self.limits:
            return True, "OK"
        
        if user_id not in self.usage:
            self.usage[user_id] = []
        
        # Clean old entries (older than 1 hour)
        now = time.time()
        self.usage[user_id] = [
            t for t in self.usage[user_id]
            if now - t < 3600
        ]
        
        limit = self.limits[user_id]
        current = len(self.usage[user_id])
        
        if current >= limit:
            return False, f"Rate limit exceeded: {current}/{limit} requests per hour"
        
        self.usage[user_id].append(now)
        return True, f"OK ({current+1}/{limit})"


import time
