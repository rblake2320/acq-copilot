"""Federal Register API tool for regulatory documents."""

from typing import Any
from datetime import datetime

from app.tools.base import BaseTool, Citation


class FederalRegisterTool(BaseTool):
    """Tool for querying Federal Register documents."""

    id = "federal_register.search_documents"
    name = "Federal Register"
    description = "Search Federal Register documents including rules, notices, and proposed rules"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_documents", "get_document"],
                "description": "The action to perform"
            },
            "term": {"type": "string", "description": "Search term"},
            "doc_type": {
                "type": "string",
                "enum": ["rule", "proposed_rule", "notice", "presidential"],
                "description": "Document type"
            },
            "agency": {"type": "string", "description": "Agency acronym or name"},
            "date_range": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                }
            },
            "document_number": {"type": "string", "description": "Document number for detail lookup"},
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "per_page": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "documents": {"type": "array"},
            "total_count": {"type": "integer"}
        }
    }
    auth_requirements = []
    rate_limit_profile = {"requests_per_minute": 1000}

    BASE_URL = "https://www.federalregister.gov/api/v1"

    async def run(self, params: dict) -> Any:
        """Execute Federal Register search or detail lookup."""
        action = params.get("action", "").lower()
        
        if action == "search_documents":
            return await self._search_documents(params)
        elif action == "get_document":
            return await self._get_document(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _search_documents(self, params: dict) -> dict:
        """Search for Federal Register documents."""
        query_params = {
            "page": params.get("page", 1),
            "per_page": params.get("per_page", 20),
        }
        
        if params.get("term"):
            query_params["conditions[term]"] = params["term"]
        
        if params.get("doc_type"):
            query_params["conditions[type]"] = params["doc_type"]
        
        if params.get("agency"):
            query_params["conditions[agencies]"] = params["agency"]
        
        if params.get("date_range"):
            start = params["date_range"].get("start_date")
            end = params["date_range"].get("end_date")
            if start:
                query_params["conditions[publication_date][gte]"] = start
            if end:
                query_params["conditions[publication_date][lte]"] = end
        
        url = f"{self.BASE_URL}/documents"
        
        response = await self._client.get(url, params=query_params)
        response.raise_for_status()
        
        data = response.json()
        
        documents = []
        for result in data.get("results", []):
            agencies = [
                {
                    "id": agency_info.get("id"),
                    "name": agency_info.get("name"),
                    "slug": agency_info.get("slug")
                }
                for agency_info in result.get("agencies", [])
            ]
            
            documents.append({
                "document_number": result.get("document_number", ""),
                "title": result.get("title", ""),
                "abstract": result.get("abstract"),
                "type": result.get("type", ""),
                "publication_date": result.get("publication_date", ""),
                "effective_date": result.get("effective_on"),
                "agencies": agencies,
                "html_url": result.get("html_url", ""),
                "pdf_url": result.get("pdf_url"),
                "comments_url": result.get("comments_url"),
                "citation": result.get("citation", ""),
            })
        
        return {
            "documents": documents,
            "total_count": data.get("total", 0),
            "page": params.get("page", 1),
            "per_page": params.get("per_page", 20)
        }

    async def _get_document(self, params: dict) -> dict:
        """Get detailed information about a specific document."""
        document_number = params.get("document_number")
        if not document_number:
            raise ValueError("document_number is required for get_document action")
        
        url = f"{self.BASE_URL}/documents/{document_number}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        
        result = response.json()
        
        agencies = [
            {
                "id": agency_info.get("id"),
                "name": agency_info.get("name"),
                "slug": agency_info.get("slug")
            }
            for agency_info in result.get("agencies", [])
        ]
        
        return {
            "document_number": result.get("document_number", ""),
            "title": result.get("title", ""),
            "abstract": result.get("abstract"),
            "type": result.get("type", ""),
            "publication_date": result.get("publication_date", ""),
            "effective_date": result.get("effective_on"),
            "agencies": agencies,
            "html_url": result.get("html_url", ""),
            "pdf_url": result.get("pdf_url"),
            "comments_url": result.get("comments_url"),
            "citation": result.get("citation", ""),
        }

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for Federal Register data."""
        citations = []
        
        if isinstance(output, dict) and "documents" in output:
            for doc in output.get("documents", []):
                if doc.get("html_url"):
                    citations.append(Citation(
                        source_name="Federal Register",
                        source_url=doc["html_url"],
                        source_label=f"Federal Register: {doc.get('title', 'Document')}",
                        retrieved_at=datetime.utcnow()
                    ))
        
        if not citations:
            citations.append(Citation(
                source_name="Federal Register",
                source_url="https://www.federalregister.gov/",
                source_label="Federal Register",
                retrieved_at=datetime.utcnow()
            ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if Federal Register API is available."""
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/documents",
                params={"per_page": 1},
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
                "action": "search_documents",
                "term": "acquisition",
                "doc_type": "rule",
                "per_page": 10
            },
            {
                "action": "search_documents",
                "agency": "GSA",
                "doc_type": "notice"
            },
            {
                "action": "get_document",
                "document_number": "2024-01234"
            }
        ]
