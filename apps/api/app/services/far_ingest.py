"""FAR/DFARS document ingestion service.

Downloads FAR XML from GitHub (GSA/GSA-Acquisition-FAR) and ingests
into the far_sections table with embeddings via Ollama nomic-embed-text.

Usage:
    python -m app.services.far_ingest  (run directly)
"""

import re
import json
import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Optional
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

logger = logging.getLogger(__name__)

# FAR GitHub raw content base
FAR_GITHUB_BASE = "https://raw.githubusercontent.com/GSA/GSA-Acquisition-FAR/main/dita"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# FAR parts to ingest (all 53 parts)
FAR_PARTS = list(range(1, 54))

# Max characters per chunk (to keep embeddings meaningful)
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


async def get_embedding(text: str, client: httpx.AsyncClient) -> Optional[list[float]]:
    """Get embedding from Ollama nomic-embed-text."""
    try:
        response = await client.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=30.0,
        )
        if response.status_code == 200:
            return response.json().get("embedding")
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
    return None


def extract_text_from_xml(xml_content: str) -> list[dict]:
    """Extract sections from FAR DITA XML.

    Returns list of dicts with: section, title, content
    """
    sections = []
    try:
        root = ET.fromstring(xml_content)
        ns = {"dita": ""}  # DITA XML may have no namespace

        # Try to find section elements
        for elem in root.iter():
            tag = elem.tag.lower().split("}")[-1]  # strip namespace
            if tag in ("section", "topic", "concept"):
                title_elem = elem.find(".//{*}title") or elem.find("title")
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"

                # Get all text content
                content_parts = []
                for child in elem.iter():
                    child_tag = child.tag.lower().split("}")[-1]
                    if child_tag in ("p", "li", "dd", "entry", "ph"):
                        if child.text:
                            content_parts.append(child.text.strip())

                content = " ".join(content_parts)
                if len(content) > 50:  # Skip tiny sections
                    sections.append({
                        "title": title,
                        "content": content,
                    })
    except ET.ParseError as e:
        logger.warning(f"XML parse error: {e}")

    return sections


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


async def fetch_far_part(part: int, client: httpx.AsyncClient) -> Optional[str]:
    """Fetch a FAR part XML from GitHub."""
    # FAR files are named like Part_001.xml, Part_015.xml, etc.
    part_str = str(part).zfill(3)
    url = f"{FAR_GITHUB_BASE}/Part_{part_str}.xml"

    try:
        response = await client.get(url, timeout=30.0)
        if response.status_code == 200:
            return response.text
        logger.debug(f"FAR Part {part}: HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"FAR Part {part} fetch error: {e}")

    return None


async def ingest_far_section(
    db: AsyncSession,
    regulation: str,
    part: int,
    section: str,
    title: str,
    content: str,
    chunk_index: int,
    source_url: str,
    client: httpx.AsyncClient,
) -> None:
    """Ingest a single FAR section chunk."""
    # Get embedding
    embed_text = f"{section}: {title}\n{content[:500]}"  # truncate for embedding
    embedding = await get_embedding(embed_text, client)

    embedding_json = json.dumps(embedding) if embedding else None

    await db.execute(
        text("""
            INSERT INTO far_sections
                (regulation, part, section, title, content, chunk_index, source_url, embedding_json, created_at)
            VALUES
                (:regulation, :part, :section, :title, :content, :chunk_index, :source_url, :embedding_json, :created_at)
            ON CONFLICT DO NOTHING
        """),
        {
            "regulation": regulation,
            "part": part,
            "section": section,
            "title": title,
            "content": content,
            "chunk_index": chunk_index,
            "source_url": source_url,
            "embedding_json": embedding_json,
            "created_at": datetime.utcnow(),
        }
    )


async def run_ingest(db_url: str, parts: Optional[list[int]] = None):
    """Main ingest function.

    Args:
        db_url: PostgreSQL connection string (asyncpg)
        parts: List of FAR parts to ingest (default: all 53)
    """
    if parts is None:
        parts = FAR_PARTS

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # Create table if not exists
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS far_sections (
                id SERIAL PRIMARY KEY,
                regulation VARCHAR(20) NOT NULL,
                part INTEGER NOT NULL,
                subpart VARCHAR(20),
                section VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT NOT NULL,
                effective_date TIMESTAMP,
                source_url VARCHAR(1000),
                chunk_index INTEGER DEFAULT 0,
                embedding_json TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_far_sections_regulation ON far_sections(regulation)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_far_sections_part ON far_sections(part)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_far_sections_section ON far_sections(section)"))

    async with httpx.AsyncClient() as client:
        for part in parts:
            logger.info(f"Ingesting FAR Part {part}...")
            xml_content = await fetch_far_part(part, client)

            if not xml_content:
                # Create a placeholder entry with FAR part overview text
                await _ingest_placeholder(part, client, async_session)
                continue

            sections = extract_text_from_xml(xml_content)
            source_url = f"https://www.acquisition.gov/far/part-{part}"

            async with async_session() as db:
                for section_data in sections:
                    chunks = chunk_text(section_data["content"])
                    for i, chunk in enumerate(chunks):
                        section_id = f"{part}.{i+1}" if len(sections) == 1 else section_data.get("id", f"{part}.x")
                        await ingest_far_section(
                            db=db,
                            regulation="FAR",
                            part=part,
                            section=f"Part {part}",
                            title=section_data["title"],
                            content=chunk,
                            chunk_index=i,
                            source_url=source_url,
                            client=client,
                        )
                await db.commit()

            logger.info(f"FAR Part {part}: {len(sections)} sections ingested")
            await asyncio.sleep(0.1)  # Rate limit Ollama

    await engine.dispose()
    logger.info("FAR ingest complete")


async def _ingest_placeholder(part: int, client: httpx.AsyncClient, async_session):
    """Ingest basic FAR part info when XML is unavailable."""
    far_part_titles = {
        1: "Federal Acquisition Regulations System",
        2: "Definitions of Words and Terms",
        3: "Improper Business Practices and Personal Conflicts of Interest",
        4: "Administrative and Information Matters",
        5: "Publicizing Contract Actions",
        6: "Competition Requirements",
        7: "Acquisition Planning",
        8: "Required Sources of Supplies and Services",
        9: "Contractor Qualifications",
        10: "Market Research",
        11: "Describing Agency Needs",
        12: "Acquisition of Commercial Products and Commercial Services",
        13: "Simplified Acquisition Procedures",
        14: "Sealed Bidding",
        15: "Contracting by Negotiation",
        16: "Types of Contracts",
        17: "Special Contracting Methods",
        18: "Emergency Acquisitions",
        19: "Small Business Programs",
        20: "Reserved",
        21: "Reserved",
        22: "Application of Labor Laws to Government Acquisitions",
        23: "Environment, Energy and Water Efficiency, Renewable Energy Technologies, Occupational Safety, and Drug-Free Workplace",
        24: "Protection of Privacy and Freedom of Information",
        25: "Foreign Acquisition",
        26: "Other Socioeconomic Programs",
        27: "Patents, Data, and Copyrights",
        28: "Bonds and Insurance",
        29: "Taxes",
        30: "Cost Accounting Standards Administration",
        31: "Contract Cost Principles and Procedures",
        32: "Contract Financing",
        33: "Protests, Disputes, and Appeals",
        34: "Major System Acquisition",
        35: "Research and Development Contracting",
        36: "Construction and Architect-Engineer Contracts",
        37: "Service Contracting",
        38: "Federal Supply Schedule Contracting",
        39: "Acquisition of Information Technology",
        40: "Reserved",
        41: "Acquisition of Utility Services",
        42: "Contract Administration and Audit Services",
        43: "Contract Modifications",
        44: "Subcontracting Policies and Procedures",
        45: "Government Property",
        46: "Quality Assurance",
        47: "Transportation",
        48: "Value Engineering",
        49: "Termination of Contracts",
        50: "Extraordinary Contractual Actions and the Safety Act",
        51: "Use of Government Sources by Contractors",
        52: "Solicitation Provisions and Contract Clauses",
        53: "Forms",
    }

    title = far_part_titles.get(part, f"FAR Part {part}")
    content = f"FAR Part {part}: {title}. This part of the Federal Acquisition Regulation covers {title.lower()}. For detailed provisions, consult the official FAR at acquisition.gov/far/part-{part}."
    source_url = f"https://www.acquisition.gov/far/part-{part}"

    async with async_session() as db:
        await ingest_far_section(
            db=db,
            regulation="FAR",
            part=part,
            section=f"Part {part}",
            title=title,
            content=content,
            chunk_index=0,
            source_url=source_url,
            client=client,
        )
        await db.commit()


if __name__ == "__main__":
    import sys
    import os

    logging.basicConfig(level=logging.INFO)

    # Get DB URL from environment
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:%3FBooker78%21@localhost:5432/postgres"
    )

    parts = None
    if len(sys.argv) > 1:
        parts = [int(p) for p in sys.argv[1:]]

    asyncio.run(run_ingest(db_url, parts))
