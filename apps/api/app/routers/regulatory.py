"""Regulatory compliance and research router."""
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import structlog

from ..tools.registry import get_registry

router = APIRouter()
logger = structlog.get_logger(__name__)


class RegulatorySearchRequest(BaseModel):
    """POST /search request body."""

    query: str
    agency: Optional[str] = None
    document_type: Optional[str] = None
    limit: int = 20
    page: int = 1


@router.post("/search")
async def search_all_regulatory_sources(request: RegulatorySearchRequest) -> dict:
    """
    Fan-out regulatory search to Federal Register, eCFR, and Regulations.gov
    in parallel and merge results.
    """
    try:
        registry = get_registry()

        fr_tool = registry.get("federal_register.search_documents")
        ecfr_tool = registry.get("ecfr.get_section")
        reg_tool = registry.get("regulations.search_dockets")

        tasks = []

        if fr_tool:
            tasks.append(
                fr_tool.execute({
                    "action": "search_documents",
                    "term": request.query,
                    "agency": request.agency,
                    "doc_type": request.document_type,
                    "per_page": request.limit,
                    "page": request.page,
                })
            )
        else:
            tasks.append(asyncio.sleep(0))  # placeholder

        if ecfr_tool:
            tasks.append(
                ecfr_tool.execute({
                    "action": "search_text",
                    "query": request.query,
                })
            )
        else:
            tasks.append(asyncio.sleep(0))

        if reg_tool:
            tasks.append(
                reg_tool.execute({
                    "action": "search_documents",
                    "search_term": request.query,
                    "agency_id": request.agency,
                    "per_page": request.limit,
                    "page": request.page,
                })
            )
        else:
            tasks.append(asyncio.sleep(0))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        fr_result = results[0] if fr_tool else None
        ecfr_result = results[1] if ecfr_tool else None
        reg_result = results[2] if reg_tool else None

        def safe_output(result, source_name):
            if result is None or isinstance(result, (Exception, type(None))):
                return {"error": str(result) if isinstance(result, Exception) else "unavailable"}
            if hasattr(result, "output"):
                return result.output or {}
            return {}

        merged = {
            "query": request.query,
            "federal_register": safe_output(fr_result, "federal_register"),
            "ecfr": safe_output(ecfr_result, "ecfr"),
            "regulations_gov": safe_output(reg_result, "regulations_gov"),
        }

        logger.info("regulatory_search_complete", query=request.query)
        return merged

    except Exception as e:
        logger.error("regulatory_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search regulatory sources",
        )


@router.get("/federal-register")
async def search_federal_register_docs(
    query: str,
    doc_type: Optional[str] = None,
    agency: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """
    Search Federal Register documents via the federal_register.search_documents tool.
    """
    try:
        registry = get_registry()
        tool = registry.get("federal_register.search_documents")

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Federal Register tool is not available",
            )

        result = await tool.execute({
            "action": "search_documents",
            "term": query,
            "doc_type": doc_type,
            "agency": agency,
            "page": page,
            "per_page": per_page,
        })

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "Federal Register search failed",
            )

        return result.output or {}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("federal_register_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search Federal Register",
        )


@router.get("/ecfr/{titleNumber}")
async def get_ecfr_title(
    titleNumber: int,
    part: Optional[int] = None,
    section: Optional[str] = None,
    query: Optional[str] = None,
) -> dict:
    """
    Get eCFR content for a given title number, with optional part/section or text search.
    """
    try:
        registry = get_registry()
        tool = registry.get("ecfr.get_section")

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="eCFR tool is not available",
            )

        if query:
            params = {"action": "search_text", "query": query, "title": titleNumber}
        else:
            params = {"action": "get_section", "title": titleNumber, "part": part, "section": section}

        result = await tool.execute(params)

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "eCFR lookup failed",
            )

        return result.output or {}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ecfr_lookup_failed", title=titleNumber, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get eCFR content",
        )


@router.get("/regulations-gov")
async def search_regulations_gov(
    query: str,
    agency_id: Optional[str] = None,
    document_type: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """
    Search Regulations.gov dockets and documents via the regulations.search_dockets tool.
    """
    try:
        registry = get_registry()
        tool = registry.get("regulations.search_dockets")

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Regulations.gov tool is not available",
            )

        result = await tool.execute({
            "action": "search_documents",
            "search_term": query,
            "agency_id": agency_id,
            "document_type": document_type,
            "page": page,
            "per_page": per_page,
        })

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error_message or "Regulations.gov search failed",
            )

        return result.output or {}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("regulations_gov_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search Regulations.gov",
        )


@router.get("/regulations/search")
async def search_regulations(query: str, agency: str = None, limit: int = 20) -> dict:
    """
    Search federal regulations using Regulations.gov API.

    Args:
        query: Search query
        agency: Optional agency code filter
        limit: Maximum results

    Returns:
        Search results
    """
    try:
        # TODO: Implement Regulations.gov API integration
        logger.info("regulations_search", query=query, agency=agency, limit=limit)
        return {
            "query": query,
            "results": [],
            "total": 0,
        }
    except Exception as e:
        logger.error("regulations_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search regulations",
        )


@router.get("/federal-register/documents")
async def search_federal_register(
    query: str,
    document_type: str = None,
    limit: int = 20,
) -> dict:
    """
    Search Federal Register documents.

    Args:
        query: Search query
        document_type: Optional document type filter
        limit: Maximum results

    Returns:
        Search results
    """
    try:
        # TODO: Implement Federal Register API integration
        logger.info(
            "federal_register_search",
            query=query,
            document_type=document_type,
            limit=limit,
        )
        return {
            "query": query,
            "results": [],
            "total": 0,
        }
    except Exception as e:
        logger.error("federal_register_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search Federal Register",
        )


@router.get("/ecfr/titles")
async def get_ecfr_titles() -> dict:
    """
    Get list of eCFR titles.

    Returns:
        List of CFR titles
    """
    try:
        # TODO: Implement eCFR API integration
        logger.info("ecfr_titles_requested")
        return {
            "titles": [],
        }
    except Exception as e:
        logger.error("ecfr_titles_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get eCFR titles",
        )


@router.get("/ecfr/search")
async def search_ecfr(query: str, title: int = None, limit: int = 20) -> dict:
    """
    Search eCFR content.

    Args:
        query: Search query
        title: Optional CFR title filter
        limit: Maximum results

    Returns:
        Search results
    """
    try:
        # TODO: Implement eCFR API integration
        logger.info("ecfr_search", query=query, title=title, limit=limit)
        return {
            "query": query,
            "results": [],
            "total": 0,
        }
    except Exception as e:
        logger.error("ecfr_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search eCFR",
        )
