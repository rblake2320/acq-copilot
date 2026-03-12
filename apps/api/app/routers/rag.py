"""RAG (Retrieval-Augmented Generation) endpoints for FAR/DFARS search."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import structlog

from ..dependencies import get_db
from ..tools.far_rag import FARRagTool

router = APIRouter()
logger = structlog.get_logger(__name__)


class RAGSearchRequest(BaseModel):
    query: str
    regulation: Optional[str] = None  # 'FAR', 'DFARS', or None
    part: Optional[int] = None
    top_k: int = 5


@router.post("/search")
async def rag_search(
    request: RAGSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search over FAR/DFARS corpus."""
    try:
        tool = FARRagTool(db=db)
        result = await tool.execute({
            "query": request.query,
            "regulation": request.regulation,
            "part": request.part,
            "top_k": request.top_k,
        })

        if result.status == "error":
            raise HTTPException(status_code=500, detail=result.error_message)

        return result.output

    except HTTPException:
        raise
    except Exception as e:
        logger.error("rag_search_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/far/{part}")
async def get_far_part(
    part: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all sections for a specific FAR part."""
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT section, title, content, source_url "
            "FROM far_sections "
            "WHERE part = :part AND regulation = 'FAR' "
            "ORDER BY chunk_index"
        ),
        {"part": part},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"FAR Part {part} not found in database")

    return {
        "part": part,
        "regulation": "FAR",
        "source_url": f"https://www.acquisition.gov/far/part-{part}",
        "sections": [
            {"section": r.section, "title": r.title, "content": r.content, "source_url": r.source_url}
            for r in rows
        ],
    }


@router.get("/status")
async def rag_status(db: AsyncSession = Depends(get_db)):
    """Check RAG corpus status."""
    from sqlalchemy import text

    try:
        result = await db.execute(
            text("SELECT regulation, COUNT(*) as cnt FROM far_sections GROUP BY regulation")
        )
        counts = {row.regulation: row.cnt for row in result.fetchall()}

        has_embeddings_result = await db.execute(
            text("SELECT COUNT(*) as cnt FROM far_sections WHERE embedding_json IS NOT NULL")
        )
        embedded = has_embeddings_result.scalar()

        return {
            "status": "ok" if counts else "empty",
            "sections_by_regulation": counts,
            "total_sections": sum(counts.values()),
            "sections_with_embeddings": embedded,
        }
    except Exception:
        return {"status": "table_not_found", "total_sections": 0}
