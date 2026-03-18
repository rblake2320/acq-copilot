"""Document parsing tool — extracts text and clauses from PDF/DOCX solicitations."""

import re
import time
import io
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
import structlog

from .base import BaseTool, ToolRunResult, Citation

logger = structlog.get_logger(__name__)


class ExtractedClause(BaseModel):
    clause_number: str  # e.g. "52.212-4"
    clause_title: Optional[str] = None
    regulation: str = "FAR"  # FAR, DFARS, GSAM
    found_at_page: Optional[int] = None
    full_text: Optional[str] = None


class DocumentParseOutput(BaseModel):
    text: str
    clauses: list[ExtractedClause]
    page_count: int
    word_count: int
    source_file: str
    parse_method: str  # "pdfplumber", "pypdf", "text"


# FAR clause pattern: e.g. 52.212-4, 52.219-14, DFARS 252.204-7012
CLAUSE_PATTERN = re.compile(
    r'\b((?:DFARS|FAR|GSAM)?\s*(?:252|52|552)\.\d{3}-\d{4}(?:\s+[A-Z][A-Za-z\s,()]+(?=\n|\.|\(|$))?)',
    re.MULTILINE
)

CLAUSE_NUMBER_PATTERN = re.compile(r'\b((?:252|52|552)\.\d{3}-\d{4})\b')

# FAR section titles dictionary (most common solicitation clauses)
FAR_CLAUSE_TITLES = {
    "52.202-1": "Definitions",
    "52.203-3": "Gratuities",
    "52.203-5": "Covenant Against Contingent Fees",
    "52.203-7": "Anti-Kickback Procedures",
    "52.203-12": "Limitation on Payments to Influence Certain Federal Transactions",
    "52.204-7": "System for Award Management",
    "52.204-10": "Reporting Executive Compensation and First-Tier Subcontract Awards",
    "52.209-6": "Protecting the Government's Interest When Subcontracting with Contractors Debarred, Suspended, or Proposed for Debarment",
    "52.212-1": "Instructions to Offerors—Commercial Products and Commercial Services",
    "52.212-2": "Evaluation—Commercial Products and Commercial Services",
    "52.212-3": "Offeror Representations and Certifications—Commercial Products and Commercial Services",
    "52.212-4": "Contract Terms and Conditions—Commercial Products and Commercial Services",
    "52.212-5": "Contract Terms and Conditions Required to Implement Statutes or Executive Orders—Commercial Products and Commercial Services",
    "52.215-1": "Instructions to Offerors—Competitive Acquisition",
    "52.215-2": "Audit and Records—Negotiation",
    "52.215-12": "Subcontractor Cost or Pricing Data",
    "52.219-1": "Small Business Program Representations",
    "52.219-4": "Notice of Price Evaluation Preference for HUBZone Small Business Concerns",
    "52.219-6": "Notice of Total Small Business Set-Aside",
    "52.219-8": "Utilization of Small Business Concerns",
    "52.219-9": "Small Business Subcontracting Plan",
    "52.219-14": "Limitations on Subcontracting",
    "52.222-21": "Prohibition of Segregated Facilities",
    "52.222-26": "Equal Opportunity",
    "52.222-35": "Equal Opportunity for Veterans",
    "52.222-36": "Equal Opportunity for Workers with Disabilities",
    "52.222-37": "Employment Reports on Veterans",
    "52.222-40": "Notification of Employee Rights Under the National Labor Relations Act",
    "52.222-50": "Combating Trafficking in Persons",
    "52.223-18": "Encouraging Contractor Policies to Ban Text Messaging While Driving",
    "52.225-13": "Restrictions on Certain Foreign Purchases",
    "52.227-11": "Patent Rights—Ownership by the Contractor",
    "52.227-14": "Rights in Data—General",
    "52.228-5": "Insurance—Work on a Government Installation",
    "52.232-1": "Payments",
    "52.232-33": "Payment by Electronic Funds Transfer—System for Award Management",
    "52.232-39": "Unenforceability of Unauthorized Obligations",
    "52.232-40": "Providing Accelerated Payments to Small Business Subcontractors",
    "52.233-1": "Disputes",
    "52.233-3": "Protest After Award",
    "52.237-2": "Protection of Government Buildings, Equipment, and Vegetation",
    "52.242-13": "Bankruptcy",
    "52.243-1": "Changes—Fixed-Price",
    "52.244-6": "Subcontracts for Commercial Products and Commercial Services",
    "52.246-4": "Inspection of Services—Fixed-Price",
    "52.249-1": "Termination for Convenience of the Government (Fixed-Price) (Short Form)",
    "52.249-8": "Default (Fixed-Price Supply and Service)",
    "52.252-1": "Solicitation Provisions Incorporated by Reference",
    "52.252-2": "Clauses Incorporated by Reference",
    # DFARS
    "252.203-7000": "Requirements Relating to Compensation of Former DoD Officials",
    "252.204-7012": "Safeguarding Covered Defense Information and Cyber Incident Reporting",
    "252.204-7015": "Notice of Authorized Disclosure of Information for Litigation Support",
    "252.204-7016": "Covered Defense Telecommunications Equipment or Services—Representation",
    "252.204-7018": "Prohibition on the Acquisition of Covered Defense Telecommunications Equipment or Services",
    "252.204-7019": "Notice of NIST SP 800-171 DoD Assessment Requirements",
    "252.204-7020": "NIST SP 800-171 DoD Assessment Requirements",
    "252.215-7013": "Supplies and Services Provided by Nontraditional Defense Contractors",
    "252.219-7003": "Small Business Subcontracting Plan (DoD Contracts)",
    "252.225-7001": "Buy American and Balance of Payments Program",
    "252.225-7048": "Export-Controlled Items",
    "252.227-7013": "Rights in Technical Data—Noncommercial Items",
    "252.227-7014": "Rights in Noncommercial Computer Software and Noncommercial Computer Software Documentation",
    "252.232-7003": "Electronic Submission of Payment Requests and Receiving Reports",
    "252.243-7001": "Pricing of Contract Modifications",
    "252.244-7000": "Subcontracts for Commercial Items",
    "252.246-7003": "Notification of Potential Safety Issues",
}


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif", "webp"}
NIM_OCR_URL = "http://localhost:8000/v1/infer"


class DocumentParseTool(BaseTool):
    """Parse PDF/DOCX/image solicitation documents to extract text and FAR clauses."""

    id = "document.parse"
    name = "Document Parser"
    description = (
        "Extract text and FAR/DFARS clauses from uploaded solicitation documents. "
        "Supports PDF, DOCX, TXT, and images (PNG, JPG, TIFF, BMP, GIF) via OCR."
    )
    auth_requirements: list = []
    rate_limit_profile: dict = {"requests_per_minute": 100}
    input_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Base64 encoded file content"},
            "filename": {"type": "string"},
            "text": {"type": "string", "description": "Raw text if already extracted"},
        },
    }
    output_schema = {"type": "object"}

    async def run(self, params: dict) -> ToolRunResult:
        start = time.time()
        filename = params.get("filename", "document")
        text = params.get("text", "")
        content_b64 = params.get("content", "")

        try:
            if not text and content_b64:
                text, page_count, method = await self._parse_file(content_b64, filename)
            else:
                page_count = 1
                method = "text"

            clauses = self._extract_clauses(text)

            output = DocumentParseOutput(
                text=text[:10000],  # Truncate for response
                clauses=clauses,
                page_count=page_count,
                word_count=len(text.split()),
                source_file=filename,
                parse_method=method,
            )

            return ToolRunResult(
                tool_id=self.id,
                input_params={"filename": filename},
                output=output.model_dump(),
                citations=[
                    Citation(
                        source_name=f"Solicitation: {filename}",
                        source_url="",
                        source_label=f"Uploaded document: {filename}",
                        retrieved_at=datetime.utcnow(),
                        snippet=f"Extracted {len(clauses)} FAR/DFARS clauses from {page_count} pages",
                    )
                ],
                duration_ms=(time.time() - start) * 1000,
                status="success",
            )

        except Exception as e:
            logger.error("document_parse_error", error=str(e))
            return ToolRunResult(
                tool_id=self.id,
                input_params={"filename": filename},
                output=None,
                citations=[],
                duration_ms=(time.time() - start) * 1000,
                status="error",
                error_message=str(e),
            )

    async def _parse_file(self, content_b64: str, filename: str):
        """Parse file content (base64 encoded)."""
        import base64
        file_bytes = base64.b64decode(content_b64)

        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

        if ext == "pdf":
            return self._parse_pdf(file_bytes)
        elif ext in ("docx", "doc"):
            return self._parse_docx(file_bytes)
        elif ext in IMAGE_EXTENSIONS:
            return await self._parse_image_ocr(file_bytes, content_b64, filename)
        elif ext == "rtf":
            return self._parse_rtf(file_bytes)
        else:
            # Treat as plain text
            try:
                text = file_bytes.decode("utf-8", errors="replace")
                return text, 1, "text"
            except Exception:
                return "", 0, "unknown"

    def _parse_pdf(self, file_bytes: bytes):
        """Parse PDF using pdfplumber (preferred) or pypdf fallback."""
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    pages.append(page_text)
            return "\n".join(pages), len(pages), "pdfplumber"
        except ImportError:
            pass

        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages), len(pages), "pypdf"
        except ImportError:
            pass

        # Last resort: try raw text extraction
        text = file_bytes.decode("utf-8", errors="replace")
        return text, 1, "raw"

    def _parse_docx(self, file_bytes: bytes):
        """Parse DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text, 1, "python-docx"
        except ImportError:
            text = file_bytes.decode("utf-8", errors="replace")
            return text, 1, "raw"

    async def _parse_image_ocr(self, file_bytes: bytes, content_b64: str, filename: str):
        """Parse image file using NVIDIA NIM PaddleOCR service."""
        import base64

        # Determine MIME type
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "png"
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "tiff": "image/tiff",
            "tif": "image/tiff", "bmp": "image/bmp",
            "gif": "image/gif", "webp": "image/webp",
        }
        mime = mime_map.get(ext, "image/png")
        data_url = f"data:{mime};base64,{content_b64}"

        try:
            payload = {
                "inputs": [
                    {
                        "name": "image",
                        "shape": [1, 1],
                        "datatype": "BYTES",
                        "data": [[data_url]],
                    }
                ]
            }
            response = await self._client.post(
                NIM_OCR_URL,
                json=payload,
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            # Extract text from NIM response
            outputs = result.get("outputs", [])
            texts = []
            for output in outputs:
                data = output.get("data", [])
                for item in data:
                    if isinstance(item, list):
                        for entry in item:
                            if isinstance(entry, str):
                                texts.append(entry)
                    elif isinstance(item, str):
                        texts.append(item)

            text = "\n".join(texts) if texts else ""
            logger.info("nim_ocr_success", filename=filename, chars=len(text))
            return text, 1, "nim-paddleocr"

        except Exception as e:
            logger.warning("nim_ocr_failed", filename=filename, error=str(e))
            # Fall back: return a placeholder so parse doesn't fail
            return (
                f"[Image file: {filename} — OCR service unavailable. "
                "Start NVIDIA NIM PaddleOCR container on port 8000 to enable image text extraction.]",
                1,
                "image-fallback",
            )

    def _parse_rtf(self, file_bytes: bytes):
        """Strip RTF markup and return plain text."""
        try:
            # Simple RTF stripper: remove control words and groups
            text = file_bytes.decode("utf-8", errors="replace")
            import re as _re
            text = _re.sub(r'\{[^{}]*\}', '', text)
            text = _re.sub(r'\\[a-z]+\d*\s?', '', text)
            text = _re.sub(r'[{}\\]', '', text)
            return text.strip(), 1, "rtf"
        except Exception:
            text = file_bytes.decode("utf-8", errors="replace")
            return text, 1, "rtf-raw"

    def _extract_clauses(self, text: str) -> list[ExtractedClause]:
        """Extract FAR/DFARS clause references from text."""
        clauses = []
        seen = set()

        for match in CLAUSE_NUMBER_PATTERN.finditer(text):
            clause_num = match.group(1)
            if clause_num in seen:
                continue
            seen.add(clause_num)

            # Determine regulation type
            if clause_num.startswith("252"):
                regulation = "DFARS"
            elif clause_num.startswith("552"):
                regulation = "GSAM"
            else:
                regulation = "FAR"

            # Look up title
            title = FAR_CLAUSE_TITLES.get(clause_num)

            # Find page number (estimate from position)
            pos = match.start()
            page_est = max(1, pos // 3000)  # rough estimate

            clauses.append(ExtractedClause(
                clause_number=clause_num,
                clause_title=title,
                regulation=regulation,
                found_at_page=page_est,
            ))

        return clauses

    def build_citations(self, params: dict, output) -> list:
        return []

    async def healthcheck(self) -> dict:
        return {"tool_id": self.id, "status": "healthy", "message": f"{self.name} is operational"}

    async def close(self) -> None:
        pass
