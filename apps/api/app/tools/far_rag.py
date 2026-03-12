"""FAR/DFARS semantic search tool using pgvector embeddings."""

import json
import time
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .base import BaseTool, ToolRunResult, Citation


OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"


class FARSearchInput(BaseModel):
    query: str = Field(..., description="Natural language search query")
    regulation: Optional[str] = Field(default=None, description="'FAR', 'DFARS', or None for all")
    part: Optional[int] = Field(default=None, description="Specific FAR part number")
    top_k: int = Field(default=5, ge=1, le=20)


class FARSearchResult(BaseModel):
    section: str
    title: str
    content: str
    regulation: str
    part: int
    source_url: str
    score: float


class FARSearchOutput(BaseModel):
    results: list[FARSearchResult]
    query: str
    total_found: int
    search_method: str  # "semantic" | "keyword" | "hybrid"


class FARRagTool(BaseTool):
    """Semantic search over FAR/DFARS using local pgvector embeddings."""

    id = "far.semantic_search"
    name = "FAR/DFARS Semantic Search"
    description = (
        "Search the full text of the Federal Acquisition Regulation (FAR) and DFARS "
        "using semantic similarity. Returns relevant sections with citations."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "regulation": {"type": "string", "enum": ["FAR", "DFARS", None]},
            "part": {"type": "integer"},
            "top_k": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object"}
    auth_requirements: list = []
    rate_limit_profile: dict = {}

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        # Do not call super().__init__() — we don't need BaseTool's httpx client
        # (we create our own per-call clients for Ollama)
        self._client = None  # satisfy BaseTool.close()
        self._db = db

    async def run(self, params: dict) -> Any:
        """Execute FAR semantic search."""
        query = params.get("query", "")
        regulation = params.get("regulation")
        part = params.get("part")
        top_k = min(params.get("top_k", 5), 20)

        results = await self._semantic_search(query, regulation, part, top_k)

        output = FARSearchOutput(
            results=results,
            query=query,
            total_found=len(results),
            search_method="semantic" if results else "keyword",
        )
        return output.model_dump()

    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """Build citations from search results."""
        if not output or not isinstance(output, dict):
            return []
        results = output.get("results", [])
        return [
            Citation(
                source_name=f"{r['regulation']} {r['section']}",
                source_url=r["source_url"],
                source_label=f"{r['regulation']} {r['section']}: {r['title']}",
                retrieved_at=datetime.utcnow(),
                snippet=r["content"][:200],
            )
            for r in results
        ]

    async def _semantic_search(
        self, query: str, regulation: Optional[str], part: Optional[int], top_k: int
    ) -> list[FARSearchResult]:
        """Search using cosine similarity on embedding_json column."""
        if not self._db:
            return await self._keyword_fallback(query, regulation, part, top_k)

        # Get query embedding
        query_embedding = await self._get_embedding(query)

        if query_embedding:
            return await self._vector_search(query, query_embedding, regulation, part, top_k)
        else:
            return await self._keyword_fallback(query, regulation, part, top_k)

    async def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding from Ollama."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    OLLAMA_EMBED_URL,
                    json={"model": EMBED_MODEL, "prompt": text},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return response.json().get("embedding")
        except Exception:
            pass
        return None

    async def _vector_search(
        self, query: str, embedding: list[float], regulation: Optional[str], part: Optional[int], top_k: int
    ) -> list[FARSearchResult]:
        """Search using stored JSON embeddings (cosine similarity in Python)."""
        # Fetch candidate rows (filter by regulation/part if specified)
        where_clauses = ["embedding_json IS NOT NULL"]
        bind_params: dict = {}

        if regulation:
            where_clauses.append("regulation = :regulation")
            bind_params["regulation"] = regulation
        if part:
            where_clauses.append("part = :part")
            bind_params["part"] = part

        where_sql = " AND ".join(where_clauses)

        result = await self._db.execute(
            text(f"""
                SELECT section, title, content, regulation, part, source_url, embedding_json
                FROM far_sections
                WHERE {where_sql}
                LIMIT 500
            """),
            bind_params,
        )
        rows = result.fetchall()

        if not rows:
            return await self._keyword_fallback(query, regulation, part, top_k)

        # Compute cosine similarity
        import math

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x * x for x in a))
            mag_b = math.sqrt(sum(x * x for x in b))
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)

        scored = []
        for row in rows:
            try:
                row_embedding = json.loads(row.embedding_json)
                score = cosine_sim(embedding, row_embedding)
                scored.append((score, row))
            except (json.JSONDecodeError, TypeError):
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top_rows = scored[:top_k]

        return [
            FARSearchResult(
                section=row.section,
                title=row.title,
                content=row.content,
                regulation=row.regulation,
                part=row.part,
                source_url=row.source_url or f"https://www.acquisition.gov/far/part-{row.part}",
                score=score,
            )
            for score, row in top_rows
        ]

    async def _keyword_fallback(
        self, query: str, regulation: Optional[str], part: Optional[int], top_k: int
    ) -> list[FARSearchResult]:
        """Full-text keyword search fallback when embeddings unavailable."""
        if not self._db:
            return []

        where_clauses = ["(LOWER(content) LIKE :q OR LOWER(title) LIKE :q)"]
        bind_params: dict = {"q": f"%{query.lower()}%"}

        if regulation:
            where_clauses.append("regulation = :regulation")
            bind_params["regulation"] = regulation
        if part:
            where_clauses.append("part = :part")
            bind_params["part"] = part

        where_sql = " AND ".join(where_clauses)

        result = await self._db.execute(
            text(f"""
                SELECT section, title, content, regulation, part, source_url
                FROM far_sections
                WHERE {where_sql}
                LIMIT :top_k
            """),
            {**bind_params, "top_k": top_k},
        )
        rows = result.fetchall()

        return [
            FARSearchResult(
                section=row.section,
                title=row.title,
                content=row.content[:1000],
                regulation=row.regulation,
                part=row.part,
                source_url=row.source_url or f"https://www.acquisition.gov/far/part-{row.part}",
                score=0.5,
            )
            for row in rows
        ]

    async def healthcheck(self) -> dict:
        return {"tool_id": self.id, "status": "ok", "name": self.name}

    async def close(self) -> None:
        pass
