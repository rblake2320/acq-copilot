"""Regulations.gov API tool for public comments and rulemaking."""

from typing import Any
from datetime import datetime

from app.tools.base import BaseTool, Citation
from app.config import settings


class RegulationsGovTool(BaseTool):
    """Tool for querying Regulations.gov documents and dockets."""

    id = "regulations.search_dockets"
    name = "Regulations.gov"
    description = "Search federal dockets, documents, and comments on Regulations.gov"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_documents", "search_dockets", "get_document"],
                "description": "The action to perform"
            },
            "search_term": {"type": "string", "description": "Search term"},
            "document_type": {"type": "string", "description": "Document type filter"},
            "agency_id": {"type": "string", "description": "Agency ID"},
            "docket_type": {"type": "string", "description": "Docket type filter"},
            "posted_date_range": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                }
            },
            "document_id": {"type": "string", "description": "Document ID for detail lookup"},
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "per_page": {"type": "integer", "default": 20, "minimum": 1, "maximum": 250},
            "api_key": {"type": "string", "description": "API key (optional)"}
        },
        "required": ["action"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "documents": {"type": "array"},
            "dockets": {"type": "array"}
        }
    }
    auth_requirements = ["api_key"]
    rate_limit_profile = {"requests_per_minute": 10}

    BASE_URL = "https://api.regulations.gov/v4"

    async def run(self, params: dict) -> Any:
        """Execute Regulations.gov search or detail lookup."""
        action = params.get("action", "").lower()
        
        if action == "search_documents":
            return await self._search_documents(params)
        elif action == "search_dockets":
            return await self._search_dockets(params)
        elif action == "get_document":
            return await self._get_document(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _search_documents(self, params: dict) -> dict:
        """Search for documents on Regulations.gov."""
        headers = self._build_headers(params.get("api_key"))
        
        query_params = {
            "page[number]": params.get("page", 1),
            "page[size]": max(5, params.get("per_page", 20)),
            "sort": "postedDate",
        }

        if params.get("search_term") or params.get("query"):
            query_params["filter[searchTerm]"] = params.get("search_term") or params.get("query")
        if params.get("document_type"):
            query_params["filter[documentType]"] = params["document_type"]
        if params.get("agency_id"):
            query_params["filter[agencyId]"] = params["agency_id"]
        if params.get("posted_date_range"):
            start = params["posted_date_range"].get("start_date")
            end = params["posted_date_range"].get("end_date")
            if start:
                query_params["filter[postedDate][ge]"] = start
            if end:
                query_params["filter[postedDate][le]"] = end

        url = f"{self.BASE_URL}/documents?" + "&".join(f"{k}={v}" for k, v in query_params.items())

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        documents = []
        for doc_data in data.get("data", []):
            attributes = doc_data.get("attributes", {})
            documents.append({
                "id": doc_data.get("id", ""),
                "title": attributes.get("title", ""),
                "type": attributes.get("documentType", ""),
                "agency": attributes.get("agencyName"),
                "docket_id": attributes.get("docketId"),
                "posted_date": attributes.get("postedDate", ""),
                "document_status": attributes.get("documentStatus", ""),
                "url": attributes.get("htmlUrl", f"https://www.regulations.gov/document/{doc_data.get('id')}"),
                "comment_end_date": attributes.get("commentEndDate"),
            })
        
        return {
            "documents": documents,
            "total_count": len(documents),
            "page": params.get("page", 1),
            "per_page": params.get("per_page", 20)
        }

    async def _search_dockets(self, params: dict) -> dict:
        """Search for dockets on Regulations.gov."""
        headers = self._build_headers(params.get("api_key"))
        
        query_params = {
            "page[number]": params.get("page", 1),
            "page[size]": max(5, params.get("per_page", 20)),
            "sort": "docketId",
        }

        if params.get("search_term") or params.get("query"):
            query_params["filter[searchTerm]"] = params.get("search_term") or params.get("query")
        if params.get("agency_id"):
            query_params["filter[agencyId]"] = params["agency_id"]
        if params.get("docket_type"):
            query_params["filter[docketType]"] = params["docket_type"]

        url = f"{self.BASE_URL}/dockets?" + "&".join(f"{k}={v}" for k, v in query_params.items())

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        dockets = []
        for docket_data in data.get("data", []):
            attributes = docket_data.get("attributes", {})
            dockets.append({
                "id": docket_data.get("id", ""),
                "title": attributes.get("title", ""),
                "type": attributes.get("docketType", ""),
                "agency": attributes.get("agencyName", ""),
                "organization": attributes.get("organizationName"),
                "document_count": attributes.get("documentCount", 0),
                "comment_count": attributes.get("commentCount", 0),
                "url": f"https://www.regulations.gov/docket/{docket_data.get('id')}"
            })
        
        return {
            "dockets": dockets,
            "total_count": len(dockets),
            "page": params.get("page", 1),
            "per_page": params.get("per_page", 20)
        }

    async def _get_document(self, params: dict) -> dict:
        """Get detailed information about a specific document."""
        document_id = params.get("document_id")
        if not document_id:
            raise ValueError("document_id is required")
        
        headers = self._build_headers(params.get("api_key"))
        
        url = f"{self.BASE_URL}/documents/{document_id}"
        
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        doc_data = data.get("data", {})
        attributes = doc_data.get("attributes", {})
        
        return {
            "id": doc_data.get("id", ""),
            "title": attributes.get("title", ""),
            "type": attributes.get("documentType", ""),
            "agency": attributes.get("agencyName"),
            "docket_id": attributes.get("docketId"),
            "posted_date": attributes.get("postedDate", ""),
            "document_status": attributes.get("documentStatus", ""),
            "url": attributes.get("htmlUrl", f"https://www.regulations.gov/document/{document_id}"),
            "comment_end_date": attributes.get("commentEndDate"),
            "attachment_count": attributes.get("attachmentCount", 0),
            "comment_count": attributes.get("commentCount", 0),
            "abstract": attributes.get("abstract"),
        }

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations for Regulations.gov data."""
        citations = []
        
        if isinstance(output, dict):
            for doc in output.get("documents", []):
                if doc.get("url"):
                    citations.append(Citation(
                        source_name="Regulations.gov",
                        source_url=doc["url"],
                        source_label=f"Regulations.gov: {doc.get('title', 'Document')}",
                        retrieved_at=datetime.utcnow()
                    ))
            
            for docket in output.get("dockets", []):
                if docket.get("url"):
                    citations.append(Citation(
                        source_name="Regulations.gov",
                        source_url=docket["url"],
                        source_label=f"Regulations.gov Docket: {docket.get('title', 'Docket')}",
                        retrieved_at=datetime.utcnow()
                    ))
        
        if not citations:
            citations.append(Citation(
                source_name="Regulations.gov",
                source_url="https://www.regulations.gov/",
                source_label="Regulations.gov",
                retrieved_at=datetime.utcnow()
            ))
        
        return citations

    async def healthcheck(self) -> dict[str, Any]:
        """Check if Regulations.gov API is available."""
        try:
            headers = self._build_headers(None)
            url = f"{self.BASE_URL}/documents?page[size]=5&sort=postedDate"
            response = await self._client.get(url, headers=headers, timeout=10.0)
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

    def _build_headers(self, api_key: str | None = None) -> dict:
        """Build request headers with API key."""
        headers = {"Content-Type": "application/json"}
        key = api_key or settings.REGULATIONS_GOV_API_KEY
        if key:
            headers["X-Api-Key"] = key
        return headers

    def get_examples(self) -> list[dict]:
        """Return example invocations."""
        return [
            {
                "action": "search_documents",
                "search_term": "federal acquisition",
                "document_type": "Public_Submission",
                "per_page": 10
            },
            {
                "action": "search_dockets",
                "agency_id": "GSAB",
                "docket_type": "Rulemaking"
            },
            {
                "action": "get_document",
                "document_id": "GSA-2024-0001"
            }
        ]
