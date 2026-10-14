"""Model clients: embeddings and text generation.

HOW IT WORKS
Two small interfaces, `Embedder` and `LLM`, with real Vertex AI implementations
(Google's `google-genai` SDK) and deterministic fakes for tests. Everything else in
the codebase depends on the interface, never on Vertex directly, so you can swap
models, or run the whole test suite offline for free.

Every LLM call returns usage (tokens in/out) and latency so the eval can report
tokens/sec and cost per request.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Protocol

EMBED_DIM = 768  # text-embedding-005 output size; must match db/migrations vector(768)

# Approximate Gemini 2.5 Flash pricing (USD per 1M tokens). Check current pricing
# before quoting cost numbers on a resume.
PRICE_IN_PER_M = 0.30
PRICE_OUT_PER_M = 2.50


@dataclass
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: float

    @property
    def cost_usd(self) -> float:
        return (self.tokens_in * PRICE_IN_PER_M + self.tokens_out * PRICE_OUT_PER_M) / 1e6

    @property
    def tokens_per_sec(self) -> float:
        return self.tokens_out / (self.latency_ms / 1000) if self.latency_ms else 0.0


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLM(Protocol):
    def complete(self, prompt: str, *, json_mode: bool = False) -> Completion: ...


# ---------------------------------------------------------------- fakes (tests)

class HashEmbedder:
    """Deterministic bag-of-words embedder. Similar texts -> similar vectors.
    Good enough to test retrieval logic without calling a paid API."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * EMBED_DIM
            for word in t.lower().split():
                h = int(hashlib.md5(word.strip(".,:;()").encode()).hexdigest(), 16)
                v[h % EMBED_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


class ScriptedLLM:
    """Returns canned responses; records prompts so tests can inspect them."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, json_mode: bool = False) -> Completion:
        self.prompts.append(prompt)
        text = self.responses.pop(0) if self.responses else "{}"
        return Completion(text=text, tokens_in=len(prompt) // 4, tokens_out=len(text) // 4,
                          latency_ms=1.0)


# ---------------------------------------------------------------- Vertex AI (prod)

class VertexEmbedder:  # pragma: no cover - needs GCP credentials
    def __init__(self, project: str, location: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 50):  # batch to stay under request limits
            resp = self._client.models.embed_content(model=self._model, contents=texts[i:i + 50])
            out.extend(e.values for e in resp.embeddings)
        return out


class VertexLLM:  # pragma: no cover - needs GCP credentials
    def __init__(self, project: str, location: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model

    def complete(self, prompt: str, *, json_mode: bool = False) -> Completion:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        start = time.perf_counter()
        resp = self._client.models.generate_content(model=self._model, contents=prompt, config=cfg)
        latency = (time.perf_counter() - start) * 1000
        usage = resp.usage_metadata
        return Completion(
            text=resp.text or "",
            tokens_in=usage.prompt_token_count or 0,
            tokens_out=usage.candidates_token_count or 0,
            latency_ms=latency,
        )
