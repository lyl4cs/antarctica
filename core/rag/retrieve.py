"""Vector store + retrieval (the "R" in RAG).

HOW IT WORKS
1. Ingest: chunk docs -> embed each chunk -> store (text, vector).
2. Query: embed the question -> find the k chunks whose vectors are closest.

DISTANCE: cosine similarity. Our embeddings are length-normalized, so cosine is
just the dot product, and pgvector's `<=>` operator returns cosine *distance*
(1 - similarity). The HNSW index (db/migrations/001) makes that search fast
without scanning every row.

WHY k=5: enough context to cover a fix from a couple of angles, small enough to
keep the prompt cheap. Check it with the eval: try k=3 and k=8 and compare.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.llm import Embedder
from core.rag.chunk import DocChunk


@dataclass
class RetrievedChunk:
    source: str
    heading: str
    text: str
    score: float  # cosine similarity, higher = more relevant


class VectorStore(Protocol):
    def add(self, chunks: list[DocChunk], vectors: list[list[float]]) -> None: ...
    def search(self, vector: list[float], k: int) -> list[RetrievedChunk]: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.items: list[tuple[DocChunk, list[float]]] = []

    def add(self, chunks, vectors) -> None:
        self.items.extend(zip(chunks, vectors))

    def search(self, vector, k) -> list[RetrievedChunk]:
        scored = [
            (sum(a * b for a, b in zip(vector, v)), c) for c, v in self.items
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [RetrievedChunk(c.source, c.heading, c.text, s) for s, c in scored[:k]]


class PgVectorStore:  # pragma: no cover - needs Postgres + pgvector
    def __init__(self, database_url: str) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self._conn = psycopg.connect(database_url, autocommit=True)
        register_vector(self._conn)

    # One long-lived connection (the API keeps it for its lifetime). Short-lived users
    # like scripts and tests should close it: `with PgVectorStore(url) as store: ...`
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PgVectorStore:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def add(self, chunks, vectors) -> None:
        import numpy as np

        with self._conn.cursor() as cur:
            for c, v in zip(chunks, vectors):
                cur.execute(
                    "INSERT INTO doc_chunks (source, ref, content, embedding) "
                    "VALUES ('doc', %s, %s, %s)",
                    (c.source, f"{c.heading}\n{c.text}" if c.heading else c.text, np.array(v)),
                )

    def search(self, vector, k) -> list[RetrievedChunk]:
        import numpy as np

        rows = self._conn.execute(
            """SELECT ref, content, 1 - (embedding <=> %s) AS sim
               FROM doc_chunks ORDER BY embedding <=> %s LIMIT %s""",
            (np.array(vector), np.array(vector), k),
        ).fetchall()
        return [RetrievedChunk(source=r[0], heading="", text=r[1], score=r[2]) for r in rows]


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder, self.store = embedder, store

    def ingest(self, chunks: list[DocChunk]) -> int:
        if not chunks:
            return 0
        vectors = self.embedder.embed([c.text for c in chunks])
        self.store.add(chunks, vectors)
        return len(chunks)

    def retrieve(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        [vector] = self.embedder.embed([query])
        return self.store.search(vector, k)
