"""Refuse to deploy code the database is not ready for.

WHY THIS EXISTS
A deploy went out ahead of its migration. The scanner's new code wrote a column
the production database did not have, every scan died on the INSERT, and because
nothing checked first, the failure surfaced an hour later as a stuck row with no
error on it. The migration itself was one command; finding out which command was
the expensive part.

Ordering like that cannot live in a person's head or in a chat message. The repo
knows which migrations exist and the database knows which ones it has applied, so
the two can be compared before anything ships.

WHAT IT CHECKS
1. Every file in db/migrations/ appears in the database's schema_migrations table.
   A file that has not been applied is a hard stop: the code about to deploy was
   written against it.
2. Rows in schema_migrations with no matching file. That means the database is
   AHEAD of this checkout, so you are deploying older code over newer schema -
   usually a stale `git pull`. Also a hard stop.

WHAT IT DOES NOT CHECK
Whether a migration's contents changed after being applied. Comparing checksums
would catch an edited migration, but AGENTS.md already forbids editing an applied
one, and a checksum column is a schema change of its own. Worth adding the day
that rule gets broken.

Run it directly to check without deploying:
    DATABASE_URL=... python infra/preflight.py
Exit code 0 means the database matches the checkout; 1 means it does not; 2 means
the check could not run (no DATABASE_URL, database unreachable), which deploy.sh
also treats as a stop, because an unverifiable deploy is the thing that hurt.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations"

OK, MISMATCH, CANNOT_CHECK = 0, 1, 2


def migration_files() -> list[str]:
    """Migration filenames in the checkout, in the order migrate.py applies them."""
    return sorted(p.name for p in MIGRATIONS.glob("*.sql"))


def applied_names(database_url: str) -> set[str]:
    """Names recorded in schema_migrations. Empty set if the table does not exist,
    which is what a database that has never been migrated looks like."""
    import psycopg

    with psycopg.connect(database_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
        ).fetchone()[0]
        if not exists:
            return set()
        return {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}


def compare(files: list[str], applied: set[str]) -> tuple[list[str], list[str]]:
    """(pending, unknown): files not yet applied, and applied names with no file.

    Pure, so the interesting part is testable without a database.
    """
    pending = [f for f in files if f not in applied]
    unknown = sorted(applied - set(files))
    return pending, unknown


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("preflight: DATABASE_URL is not set, cannot verify the schema", file=sys.stderr)
        return CANNOT_CHECK

    files = migration_files()
    try:
        applied = applied_names(database_url)
    except Exception as e:  # noqa: BLE001 - any connection failure is the same answer
        print(f"preflight: could not reach the database: {e}", file=sys.stderr)
        return CANNOT_CHECK

    pending, unknown = compare(files, applied)

    if pending:
        print(
            "preflight: the database is missing migrations this code needs:\n"
            + "\n".join(f"  - {p}" for p in pending)
            + "\n\nRun them first:\n"
            "  DATABASE_URL=... python infra/migrate.py",
            file=sys.stderr,
        )
        return MISMATCH

    if unknown:
        print(
            "preflight: the database has migrations this checkout does not:\n"
            + "\n".join(f"  - {u}" for u in unknown)
            + "\n\nYou are about to deploy older code over a newer schema. "
            "Pull the branch that owns these first.",
            file=sys.stderr,
        )
        return MISMATCH

    print(f"preflight: schema matches ({len(files)} migrations applied)")
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
