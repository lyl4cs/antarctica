"""Apply db/migrations/*.sql in order, once each. Run: DATABASE_URL=... python infra/migrate.py

Tracks applied files in a `schema_migrations` table so re-running is safe.
Each file runs inside its own transaction: if a migration fails halfway, nothing
from it is kept and it is not recorded, so you can fix it and re-run.
The integration tests call `apply_migrations` directly, so tests and production
build the schema the exact same way.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations"


def apply_migrations(database_url: str) -> list[str]:
    """Apply pending migrations and return the names of the ones applied this run."""
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
        done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name in done:
                continue
            with conn.transaction():
                conn.execute(f.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
            applied.append(f.name)
    return applied


def main() -> None:
    for name in apply_migrations(os.environ["DATABASE_URL"]):
        print(f"applied {name}")
    print("migrations up to date")


if __name__ == "__main__":
    main()
