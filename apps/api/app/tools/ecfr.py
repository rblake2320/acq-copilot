"""eCFR (Electronic Code of Federal Regulations) tool."""

from typing import Any
from datetime import datetime

from app.tools.base import BaseTool, Citation


class eCFRTool(BaseTool):
    """Tool for querying the Electronic Code of Federal Regulations."""

    id = "ecfr.get_section"
    name = "eCFR"
    description = "Get CFR sections, search regulations, and compare versions"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_section", "search_text", "compare_versions"],
                "description": "The action to perform"
            },
            "title": {"type": "integer", "minimum": 1, "maximum": 50, "description": "CFR title"},
            "part": {"type": "integer", "description": "Part number"},
            "section": {"type": "string", "description": "Section number"},
            "query": {"type": "string", "description": "Search query"},
            "date": {"type": "string", "description": "Specific date for historical version"},
            "date1": {"type": "string", "description": "Start date for comparison"},
            "date2": {"type": "string", "description": "End date for comparison"}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "integer"},
            "part": {"type": "integer"},
            "section": {"type": "string"},
            "text": {"type": "string"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 1000}

    BASE_URL = "https://www.ecfr.gov/api/versioner/v1"

    async def run(self, params: dict) -> Any:
        """Execute eCFR lookup or search."""
        action = params.get("action", "").lower()
        
        if action == "get_section":
            return await self._get_section(params)
        elif action == "search_text":
            return await self._search_text(params)
        elif action == "compare_versions":
            return await self._compare_versions(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _get_section(self, params: dict) -> dict:
        """Get a specific CFR section using eCFR search API."""
        title = params.get("title")
        part = params.get("part")
        section = params.get("section")

        if not title:
            raise ValueError("title is required")

        # Build search query to find specific section
        query_parts = []
        if part and section:
            query_parts.append(f"{part}.{section}")
        elif part:
            query_parts.append(f"part {part}")

        q = " ".join(query_parts) if query_parts else "federal acquisition"

        search_params: dict = {"query": q, "per_page": 5}
        if title:
            search_params["hierarchy[title]"] = str(title)
        if part:
            search_params["hierarchy[part]"] = str(part)

        url = "https://www.ecfr.gov/api/search/v1/results"
        response = await self._client.get(url, params=search_params)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            return {
                "title": title, "part": part, "section": section,
                "heading": "", "text": "No content found for this section.",
                "citation": f"{title} CFR {part}.{section}" if part and section else f"Title {title}",
                "url": f"https://www.ecfr.gov/current/title-{title}" + (f"/part-{part}" if part else "")
            }

        r = results[0]
        h = r.get("hierarchy_headings", {})
        return {
            "title": title,
            "part": part,
            "section": r.get("hierarchy", {}).get("section", section),
            "heading": h.get("section", h.get("part", "")),
            "text": r.get("full_text_excerpt", "").replace("<strong>", "").replace("</strong>", ""),
            "citation": f"{title} CFR {r.get('hierarchy', {}).get('part', part)}.{r.get('hierarchy', {}).get('section', section)}",
            "url": f"https://www.ecfr.gov/current/title-{title}" + (f"/part-{r.get('hierarchy', {}).get('part', part)}" if part else ""),
            "total_results": data.get("meta", {}).get("total_count", len(results))
        }

    async def _search_text(self, params: dict) -> dict:
        """Search eCFR for regulations matching a query."""
        query = params.get("query")
        if not query:
            raise ValueError("query is required")

        search_params: dict = {"query": query, "per_page": 10}
        if params.get("title"):
            search_params["hierarchy[title]"] = str(params["title"])

        url = "https://www.ecfr.gov/api/search/v1/results"
        response = await self._client.get(url, params=search_params)
        response.raise_for_status()

        data = response.json()
        results = []
        for r in data.get("results", []):
            h = r.get("hierarchy", {})
            hh = r.get("hierarchy_headings", {})
            results.append({
                "title": h.get("title", ""),
                "part": h.get("part", ""),
                "section": h.get("section", ""),
                "heading": hh.get("section", hh.get("part", "")),
                "excerpt": r.get("full_text_excerpt", "").replace("<strong>", "").replace("</strong>", ""),
                "url": f"https://www.ecfr.gov/current/title-{h.get('title','')}/part-{h.get('part','')}" if h.get("title") else ""
            })

        return {
            "results": results,
            "total": data.get("meta", {}).get("total_count", len(results))
        }

    async def _compare_versions(self, params: dict) -> dict:
        """Compare two versions of a CFR section."""
        title = params.get("title")
        part = params.get("part")
        section = params.get("section")
        date1 = params.get("date1")
        date2 = params.get("date2")
        
        if not all([title, part, section, date1, date2]):
            raise ValueError("title, part, section, date1, and date2 are required")
        
        # Get version 1
        url1 = f"{self.BASE_URL}/sections/{title}-{part}.{section}.json?date={date1}"
        response1 = await self._client.get(url1)
        response1.raise_for_status()
        data1 = response1.json()
        text1 = data1.get("section", {}).get("text", "")
        
        # Get version 2
        url2 = f"{self.BASE_URL}/sections/{title}-{part}.{section}.json?date={date2}"
        response2 = await self._client.get(url2)
        response2.raise_for_status()
        data2 = response2.json()
        text2 = data2.get("section", {}).get("text", "")
        
        changes_summary = "No changes between the two dates" if text1 == text2 else f"Section content differs between {date1} and {date2}"
        
        return {
            "title": title,
            "part": part,
            "section": section,
            "date1": date1,
            "date2": date2,
            "changes_summary": changes_summary,
            "before_text": text1 if text1 != text2 else None,
            "after_text": text2 if text1 != text2 else None,
        }

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for eCFR data."""
        citations = []
        action = params.get("action", "").lower()
        
        if action == "get_section":
            title = params.get("title")
            part = params.get("part")
            section = params.get("section")
            if all([title, part, section]):
                url = f"https://www.ecfr.gov/current/title-{title}/part-{part}/section-{section}"
                citations.append(Citation(
                    source_name="eCFR",
                    source_url=url,
                    source_label=f"{title} CFR {part}.{section}",
                    retrieved_at=datetime.utcnow()
                ))
        
        if not citations:
            citations.append(Citation(
                source_name="eCFR",
                source_url="https://www.ecfr.gov/",
                source_label="Electronic Code of Federal Regulations",
                retrieved_at=datetime.utcnow()
            ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if eCFR API is available."""
        try:
            response = await self._client.get(
                "https://www.ecfr.gov/api/search/v1/results",
                params={"query": "acquisition", "per_page": 1},
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
                "action": "get_section",
                "title": 48,
                "part": 1,
                "section": "101"
            },
            {
                "action": "search_text",
                "query": "federal acquisition",
                "title": 48
            },
            {
                "action": "compare_versions",
                "title": 48,
                "part": 1,
                "section": "101",
                "date1": "2024-01-01",
                "date2": "2024-12-31"
            }
        ]
