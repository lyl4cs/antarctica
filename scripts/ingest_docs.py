"""Chunk + embed data/docs/*.md into pgvector.  Run once after fetch_docs.py.

    python scripts/ingest_docs.py            # real: Vertex embeddings -> Neon
    python scripts/ingest_docs.py --dry-run  # just print chunk counts, no API calls
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.rag.chunk import chunk_markdown

DOCS = Path("data/docs")


def load_chunks():
    chunks = []
    for f in sorted(DOCS.glob("*.md")):
        text = f.read_text()
        first, _, body = text.partition("\n")
        source = first.removeprefix("Source:").strip() if first.startswith("Source:") else f.name
        chunks.extend(chunk_markdown(body, source))
    return chunks


def main() -> None:  # pragma: no cover
    chunks = load_chunks()
    print(f"{len(chunks)} chunks from {len(list(DOCS.glob('*.md')))} docs")
    if "--dry-run" in sys.argv:
        return
    from core.llm import VertexEmbedder
    from core.rag.retrieve import PgVectorStore, Retriever
    from services.common.config import get_settings

    s = get_settings()
    r = Retriever(VertexEmbedder(s.project_id, s.region, s.embed_model),
                  PgVectorStore(s.database_url))
    print(f"ingested {r.ingest(chunks)} chunks")


if __name__ == "__main__":
    main()
