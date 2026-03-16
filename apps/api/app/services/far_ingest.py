"""FAR/DFARS document ingestion service.

Fetches all DITA section files from GSA/GSA-Acquisition-FAR on GitHub and
ingests them into the far_sections table with pgvector embeddings.

Each file is an individual FAR section (e.g. 15.101-1.dita = FAR 15.101-1).

Usage:
    python -m app.services.far_ingest          # all 3,900+ sections
    python -m app.services.far_ingest 1 2 7    # specific parts only
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

FAR_GITHUB_API = "https://api.github.com/repos/GSA/GSA-Acquisition-FAR/git/trees/master?recursive=1"
FAR_RAW_BASE = "https://raw.githubusercontent.com/GSA/GSA-Acquisition-FAR/master/dita"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# Max workers for concurrent embedding+fetch
CONCURRENCY = 8


async def get_embedding(txt: str, client: httpx.AsyncClient) -> Optional[list[float]]:
    """Get embedding from Ollama nomic-embed-text."""
    try:
        response = await client.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": txt},
            timeout=30.0,
        )
        if response.status_code == 200:
            return response.json().get("embedding")
    except Exception as e:
        logger.debug(f"Embedding failed: {e}")
    return None


def parse_dita(xml_content: str, filename: str) -> Optional[dict]:
    """Parse a FAR DITA section file.

    Returns dict with: section, title, content, part
    """
    # Derive section number from filename: "15.101-1.dita" -> "15.101-1"
    section = filename.replace(".dita", "")

    # Strip DOCTYPE declaration — ET can't fetch the external DTD
    xml_clean = re.sub(r'<!DOCTYPE[^>]*(?:>|(?:\[[^\]]*\])\s*>)', '', xml_content)

    try:
        root = ET.fromstring(xml_clean)
    except ET.ParseError as e:
        logger.debug(f"XML parse error for {filename}: {e}")
        return None

    # Extract title — look for <ph props="autonumber"> inside <title>
    title = ""
    for title_elem in root.iter():
        tag = title_elem.tag.split("}")[-1].lower()
        if tag == "title":
            # Get text content, stripping the section number from ph
            parts = []
            if title_elem.text:
                parts.append(title_elem.text.strip())
            for child in title_elem:
                child_tag = child.tag.split("}")[-1].lower()
                if child_tag == "ph" and child.get("props") == "autonumber":
                    # Skip — this is just the section number
                    if child.tail:
                        parts.append(child.tail.strip())
                else:
                    if child.text:
                        parts.append(child.text.strip())
                    if child.tail:
                        parts.append(child.tail.strip())
            title = " ".join(p for p in parts if p).strip()
            break

    if not title:
        title = f"FAR {section}"

    # Extract body text
    content_parts = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag in ("p", "li", "dd", "entry", "ph", "keyword", "term"):
            if elem.text and elem.text.strip():
                content_parts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                content_parts.append(elem.tail.strip())

    content = " ".join(content_parts)

    if len(content) < 10:
        return None  # empty section

    # Derive part number
    part_match = re.match(r"^(\d+)", section)
    part = int(part_match.group(1)) if part_match else 0

    return {
        "section": section,
        "title": title.strip(),
        "content": content,
        "part": part,
    }


async def fetch_dita_file_list(client: httpx.AsyncClient, parts_filter: Optional[list[int]] = None) -> list[str]:
    """Get list of all DITA filenames from GitHub."""
    logger.info("Fetching FAR file index from GitHub...")
    response = await client.get(FAR_GITHUB_API, timeout=30.0)
    response.raise_for_status()

    tree = response.json().get("tree", [])
    dita_files = [
        item["path"].split("/")[-1]
        for item in tree
        if item["path"].startswith("dita/") and item["path"].endswith(".dita")
    ]

    if parts_filter:
        dita_files = [
            f for f in dita_files
            if (m := re.match(r"^(\d+)", f)) and int(m.group(1)) in parts_filter
        ]

    logger.info(f"Found {len(dita_files)} DITA section files")
    return sorted(dita_files)


async def ingest_section(
    db: AsyncSession,
    section_data: dict,
    embedding: Optional[list[float]],
) -> None:
    """Upsert a single FAR section."""
    embedding_json = json.dumps(embedding) if embedding else None
    source_url = f"https://www.acquisition.gov/far/part-{section_data['part']}#{section_data['section'].replace('.', '_')}"

    await db.execute(
        text("""
            INSERT INTO far_sections
                (regulation, part, section, title, content, chunk_index, source_url, embedding_json, created_at)
            VALUES
                (:regulation, :part, :section, :title, :content, 0, :source_url, :embedding_json, :created_at)
            ON CONFLICT DO NOTHING
        """),
        {
            "regulation": "FAR",
            "part": section_data["part"],
            "section": section_data["section"],
            "title": section_data["title"],
            "content": section_data["content"],
            "source_url": source_url,
            "embedding_json": embedding_json,
            "created_at": datetime.utcnow(),
        },
    )


async def process_file(
    filename: str,
    http_client: httpx.AsyncClient,
    make_session,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Fetch, parse, embed, and store one DITA file (own session per task)."""
    async with semaphore:
        try:
            url = f"{FAR_RAW_BASE}/{filename}"
            response = await http_client.get(url, timeout=20.0)
            if response.status_code != 200:
                return False

            section_data = parse_dita(response.text, filename)
            if not section_data:
                return False

            # Embed: section number + title + start of content
            embed_text = f"FAR {section_data['section']}: {section_data['title']}\n{section_data['content'][:800]}"
            embedding = await get_embedding(embed_text, http_client)

            async with make_session() as db:
                await ingest_section(db, section_data, embedding)
                await db.commit()
            return True
        except Exception as e:
            logger.warning(f"Error processing {filename}: {e}")
            return False


async def run_ingest(db_url: str, parts: Optional[list[int]] = None):
    """Main ingest function.

    Args:
        db_url: PostgreSQL asyncpg connection string
        parts: Specific FAR part numbers to ingest (default: all)
    """
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
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(regulation, section, chunk_index)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_far_sections_regulation ON far_sections(regulation)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_far_sections_part ON far_sections(part)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_far_sections_section ON far_sections(section)"))

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient() as http_client:
        filenames = await fetch_dita_file_list(http_client, parts)

        done = 0
        errors = 0
        batch_size = 50

        for i in range(0, len(filenames), batch_size):
            batch = filenames[i:i + batch_size]
            tasks = [
                process_file(fn, http_client, async_session, semaphore)
                for fn in batch
            ]
            results = await asyncio.gather(*tasks)
            done += sum(results)
            errors += sum(1 for r in results if not r)

            if (i // batch_size) % 5 == 0:
                logger.info(f"Progress: {done}/{len(filenames)} sections ingested, {errors} skipped")

    await engine.dispose()
    logger.info(f"FAR ingest complete: {done} sections, {errors} skipped")
    return done


if __name__ == "__main__":
    import sys
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:%3FBooker78%21@localhost:5432/postgres"
    )

    parts = [int(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else None
    asyncio.run(run_ingest(db_url, parts))
