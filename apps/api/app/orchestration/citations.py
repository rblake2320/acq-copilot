"""Citation aggregation and formatting.

This module collects citations from all tool runs, deduplicates,
and formats them for display.
"""

from typing import Optional, Any
from pydantic import BaseModel
from dataclasses import dataclass
from urllib.parse import urlparse

from .executor import ToolRunResult


@dataclass
class Citation:
    """Single citation reference."""
    ref_number: int
    source_name: str
    source_url: Optional[str] = None
    tool_id: str = ""
    access_date: str = ""
    description: str = ""
    
    def format_chicago(self) -> str:
        """Format as Chicago style citation."""
        if self.source_url:
            return f"{self.source_name}. Accessed {self.access_date}. {self.source_url}"
        return f"{self.source_name}. Accessed {self.access_date}."
    
    def format_plain(self) -> str:
        """Format as plain text citation."""
        if self.source_url:
            return f"[{self.ref_number}] {self.source_name}: {self.source_url}"
        return f"[{self.ref_number}] {self.source_name}"
    
    def format_html(self) -> str:
        """Format as HTML citation."""
        if self.source_url:
            return (
                f'<li id="cite-{self.ref_number}">'
                f'<a href="{self.source_url}">{self.source_name}</a>'
                f' (accessed {self.access_date})</li>'
            )
        return f'<li id="cite-{self.ref_number}">{self.source_name}</li>'


class CitationAggregator:
    """Aggregates and manages citations from tool results.
    
    Features:
    - Extracts citations from tool outputs
    - Deduplicates by source URL
    - Assigns reference numbers
    - Formats for different output styles
    - Tracks citation metadata
    """
    
    # Tool to source name mappings
    TOOL_SOURCE_NAMES = {
        "usaspending_search": "USAspending.gov",
        "usaspending_detail": "USAspending.gov",
        "far_lookup": "Federal Acquisition Regulation (FAR)",
        "far_search": "Federal Acquisition Regulation (FAR)",
        "far_compare": "Federal Acquisition Regulation (FAR)",
        "bls_wage": "Bureau of Labor Statistics",
        "gsa_perdiem": "GSA Per Diem Rates",
        "federalregister_search": "Federal Register",
        "market_research": "Market Research",
        "general_knowledge": "General Acquisition Knowledge",
    }
    
    # Tool to default URLs
    TOOL_BASE_URLS = {
        "usaspending_search": "https://www.usaspending.gov",
        "usaspending_detail": "https://www.usaspending.gov",
        "far_lookup": "https://www.acquisition.gov/far",
        "far_search": "https://www.acquisition.gov/far",
        "far_compare": "https://www.acquisition.gov/far",
        "bls_wage": "https://www.bls.gov/oes",
        "gsa_perdiem": "https://www.gsa.gov/travel/plan-a-trip/per-diem-rates",
        "federalregister_search": "https://www.regulations.gov",
        "market_research": "",
        "general_knowledge": "",
    }

    def __init__(self):
        """Initialize citation aggregator."""
        self.citations: list[Citation] = []
        self._seen_urls: set[str] = set()

    def add_from_result(
        self,
        result: ToolRunResult,
        access_date: str = ""
    ) -> Optional[int]:
        """Add citations from a tool result.
        
        Args:
            result: ToolRunResult with potential citation data
            access_date: Access date string (ISO format recommended)
            
        Returns:
            Reference number if citation added, None otherwise
        """
        source_name = self.TOOL_SOURCE_NAMES.get(result.tool_id, result.tool_id)
        source_url = self._extract_url(result)
        
        if not source_url:
            source_url = self.TOOL_BASE_URLS.get(result.tool_id)
        
        # Check for duplicates
        url_key = source_url or source_name
        if url_key in self._seen_urls:
            return None
        
        self._seen_urls.add(url_key)
        
        citation = Citation(
            ref_number=len(self.citations) + 1,
            source_name=source_name,
            source_url=source_url,
            tool_id=result.tool_id,
            access_date=access_date or "current date",
            description=self._extract_description(result)
        )
        
        self.citations.append(citation)
        return citation.ref_number

    def add_multiple(
        self,
        results: list[ToolRunResult],
        access_date: str = ""
    ) -> dict[str, int]:
        """Add citations from multiple results.
        
        Args:
            results: List of ToolRunResults
            access_date: Access date for all
            
        Returns:
            Map of tool_id -> reference number
        """
        ref_map = {}
        for result in results:
            ref = self.add_from_result(result, access_date)
            if ref:
                ref_map[result.tool_id] = ref
        return ref_map

    def get_all(self) -> list[Citation]:
        """Get all aggregated citations.
        
        Returns:
            List of Citation objects
        """
        return self.citations.copy()

    def get_formatted(self, style: str = "plain") -> list[str]:
        """Get formatted citations.
        
        Args:
            style: Format style - "plain", "chicago", or "html"
            
        Returns:
            List of formatted citation strings
        """
        if style == "chicago":
            return [c.format_chicago() for c in self.citations]
        elif style == "html":
            return [c.format_html() for c in self.citations]
        else:  # plain
            return [c.format_plain() for c in self.citations]

    def get_reference(self, tool_id: str) -> Optional[int]:
        """Get reference number for a tool.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            Reference number or None
        """
        for citation in self.citations:
            if citation.tool_id == tool_id:
                return citation.ref_number
        return None

    def format_bibliography(self, style: str = "plain") -> str:
        """Format complete bibliography.
        
        Args:
            style: Format style - "plain", "chicago", or "html"
            
        Returns:
            Formatted bibliography string
        """
        if style == "html":
            return "<ol>" + "\n".join(self.get_formatted(style)) + "</ol>"
        else:
            return "\n".join(self.get_formatted(style))

    def embed_references(
        self,
        text: str,
        ref_map: dict[str, int]
    ) -> str:
        """Embed reference numbers in text.
        
        Args:
            text: Original text
            ref_map: Map of source -> reference number
            
        Returns:
            Text with embedded references like [1], [2]
        """
        result = text
        
        for source, ref_num in sorted(ref_map.items(), key=lambda x: -len(x[0])):
            # Replace source mentions with references
            # This is a simple approach; more sophisticated matching could be used
            patterns = [
                f"from {source}",
                f"according to {source}",
                f"{source} shows",
            ]
            
            for pattern in patterns:
                if pattern.lower() in result.lower():
                    # Replace first occurrence
                    result = result.replace(
                        pattern,
                        f"{pattern}[{ref_num}]",
                        1
                    )
        
        return result

    def _extract_url(self, result: ToolRunResult) -> Optional[str]:
        """Extract URL from result data.
        
        Args:
            result: ToolRunResult
            
        Returns:
            URL string or None
        """
        if result.data is None:
            return None
        
        if isinstance(result.data, dict):
            # Try common URL field names
            for key in ["url", "source_url", "link", "href"]:
                if key in result.data:
                    return result.data[key]
        
        if isinstance(result.data, list) and result.data:
            # Check first item if it's a dict
            first = result.data[0]
            if isinstance(first, dict):
                for key in ["url", "source_url", "link"]:
                    if key in first:
                        return first[key]
        
        return None

    def _extract_description(self, result: ToolRunResult) -> str:
        """Extract description from result data.
        
        Args:
            result: ToolRunResult
            
        Returns:
            Description string
        """
        if result.data is None:
            return ""
        
        if isinstance(result.data, dict):
            if "title" in result.data:
                return result.data["title"]
            if "description" in result.data:
                return result.data["description"]
            if "summary" in result.data:
                return result.data["summary"]
        
        return ""

    def clear(self) -> None:
        """Clear all citations."""
        self.citations.clear()
        self._seen_urls.clear()

    def count(self) -> int:
        """Get citation count.
        
        Returns:
            Number of citations
        """
        return len(self.citations)
