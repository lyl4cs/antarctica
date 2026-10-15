"""Fixtures for tests that hit a REAL Postgres + pgvector.

WHY THESE EXIST
The unit tests use InMemoryStore, which can't catch SQL bugs: a typo in a column
name, a wrong JOIN, or a broken row lock. These tests run the actual SQL.

They are skipped unless TEST_DATABASE_URL is set, so `pytest` still works offline
with zero setup. CI sets it in a separate job with a Postgres service container.
"""

from __future__ import annotations

import os

import pytest

DB_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def db_url() -> str:
    if not DB_URL:
        pytest.skip("TEST_DATABASE_URL not set (see docker-compose.yml)")
    from infra.migrate import apply_migrations

    apply_migrations(DB_URL)  # same code path as production
    return DB_URL


@pytest.fixture
def clean_db(db_url: str) -> str:
    """Empty every data table before each test so tests can't leak into each other."""
    import psycopg

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("TRUNCATE scans, audits, findings, doc_chunks, sites, rate_counters RESTART IDENTITY CASCADE")
    return db_url
