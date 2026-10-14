"""All configuration comes from environment variables (12-factor style).

Why: the same container image runs locally, in CI, and on Cloud Run. Only the
environment changes. Secrets never live in the code or the repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    project_id: str
    region: str
    scan_topic: str
    embed_model: str
    llm_model: str
    max_scan_attempts: int


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        project_id=os.environ.get("PROJECT_ID", ""),
        region=os.environ.get("REGION", "us-central1"),
        scan_topic=os.environ.get("SCAN_TOPIC", "scans"),
        embed_model=os.environ.get("VERTEX_EMBED_MODEL", "text-embedding-005"),
        llm_model=os.environ.get("VERTEX_LLM_MODEL", "gemini-2.5-flash"),
        max_scan_attempts=int(os.environ.get("MAX_SCAN_ATTEMPTS", "3")),
    )
