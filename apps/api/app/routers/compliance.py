"""Solicitation compliance checking endpoints."""

import base64
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from ..tools.document_parse import DocumentParseTool
from ..tools.compliance_checker import ComplianceCheckerTool

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/check")
async def check_compliance(
    file: UploadFile = File(...),
    contract_type: Optional[str] = Form(default=""),
):
    """
    Upload a solicitation document (PDF/DOCX) and get a FAR compliance report.

    Returns:
    - Compliance score (0-100)
    - Grade (A-F)
    - List of clauses found
    - Missing required clauses with FAR citations
    - Recommendations
    """
    try:
        # Read and encode file
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")

        content_b64 = base64.b64encode(file_bytes).decode()

        # Step 1: Parse document
        parse_tool = DocumentParseTool()
        parse_result = await parse_tool.run({
            "content": content_b64,
            "filename": file.filename or "document.pdf",
        })

        if parse_result.status == "error":
            raise HTTPException(status_code=422, detail=f"Could not parse document: {parse_result.error_message}")

        parse_output = parse_result.output
        clauses_found = [c["clause_number"] for c in parse_output.get("clauses", [])]
        full_text = parse_output.get("text", "")

        # Step 2: Run compliance check
        check_tool = ComplianceCheckerTool()
        check_result = await check_tool.run({
            "clauses_found": clauses_found,
            "full_text": full_text,
            "contract_type": contract_type,
        })

        if check_result.status == "error":
            raise HTTPException(status_code=500, detail=check_result.error_message)

        return {
            "filename": file.filename,
            "parse": {
                "clauses_extracted": len(clauses_found),
                "page_count": parse_output.get("page_count", 1),
                "word_count": parse_output.get("word_count", 0),
                "parse_method": parse_output.get("parse_method"),
                "clauses": parse_output.get("clauses", []),
            },
            "compliance": check_result.output,
            "citations": [c.model_dump() for c in check_result.citations],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("compliance_check_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


class TextComplianceRequest(BaseModel):
    text: str
    filename: str = "solicitation"
    contract_type: str = ""


@router.post("/check-text")
async def check_compliance_text(request: TextComplianceRequest):
    """Check compliance from pasted/extracted text (no file upload required)."""
    try:
        parse_tool = DocumentParseTool()
        parse_result = await parse_tool.run({
            "text": request.text,
            "filename": request.filename,
        })

        parse_output = parse_result.output or {}
        clauses_found = [c["clause_number"] for c in parse_output.get("clauses", [])]

        check_tool = ComplianceCheckerTool()
        check_result = await check_tool.run({
            "clauses_found": clauses_found,
            "full_text": request.text,
            "contract_type": request.contract_type,
        })

        return {
            "parse": {
                "clauses_extracted": len(clauses_found),
                "clauses": parse_output.get("clauses", []),
            },
            "compliance": check_result.output,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
