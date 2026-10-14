"""RAG retrieval. OWNER ONLY (Layth writes this, not agents).

You'll be asked about every line of this in interviews. Before you code, answer
these in a comment block at the top of the file:
  1. What are you chunking (web.dev articles? past findings?), and how big is each chunk? Why?
  2. Which embedding model, and how many dimensions? (Vertex text-embedding-005 = 768)
  3. Cosine or L2 distance? Why does it matter for normalized embeddings?
  4. What top-k, and how did you pick it? (Measure it with core/evals, don't guess.)
  5. How do structured data (audit JSON) and unstructured data (docs) get combined in one query?
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    id: str
    source: str  # "doc" | "finding"
    text: str
    score: float  # similarity, higher = more relevant


def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with Vertex AI. Returns one vector per text."""
    raise NotImplementedError


def retrieve(query: str, k: int = 5) -> list[Chunk]:
    """Return the top-k chunks for a query from the doc_chunks table (pgvector)."""
    raise NotImplementedError
