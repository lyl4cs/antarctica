"""Report a scan that never came back as failed, instead of as still running.

THE BUG THIS EXISTS FOR
The scanner marks a scan `running` before it starts work, then writes either a
result or an error when it finishes. Both of those writes live in the same
process. If that process dies hard - an OOM kill, an evicted container, a Cloud
Run timeout - neither one happens. The row keeps whatever `start_attempt` wrote
and stays `running` forever.

Nothing downstream copes with that. Pub/Sub stops after `--max-delivery-attempts`
and sends the message to the dead-letter topic, so no retry will ever revisit the
row. The scan page polls `/scans/{id}` every 2 s for as long as the status is
queued or running, so a browser left open polls a dead scan indefinitely, against
a service billed per request. The history list shows it as in-flight for good.

This was not theoretical: a scanner image that OOM-killed on every request left a
scan at `attempts: 5, status: running, error: null`, five being the subscription's
delivery limit rather than anything the worker chose.

HOW IT WORKS
A scan that has been queued or running for longer than `after_s` is *reported* as
failed. One pure function, applied where the store turns rows into `Scan` objects,
so every read path gets it: the scan itself, the site history, and the report
endpoint's 409.

WHY DERIVE IT INSTEAD OF WRITING IT
Nothing is written to the database, which is what makes an aggressive threshold
safe. If a late delivery does succeed after all, `save_result` sets the row to
`done` and this function stops applying, so the scan simply appears as the success
it turned out to be. A background job that wrote `failed` into the row would have
to be correct about a race it cannot see; this cannot be wrong for longer than it
takes the next read to happen.

CHOOSING THE THRESHOLD
The worst honest case is every delivery burning the full Cloud Run request timeout
before being retried: 5 attempts x 300 s, plus roughly 150 s of 10/20/40/80 s
backoff, is about 27 minutes. The default here is deliberately shorter than that.
A scan still being retried at the 15 minute mark has no reader left, and the
non-destructive design above means being early costs nothing while being late
means a spinner that never stops.
"""

from __future__ import annotations

from datetime import UTC, datetime

from services.common.models import Scan

#: Seconds a scan may sit in a non-terminal state before it is reported failed.
DEFAULT_STALE_AFTER_S = 900

#: Shown to the user in place of an error the worker never got to write.
STALE_ERROR = (
    "The scanner stopped responding and this scan was never finished. "
    "Nothing was measured. Try scanning again."
)

#: Statuses that are still waiting on the scanner, and so can go stale.
PENDING_STATUSES = ("queued", "running")


def is_stale(scan: Scan, now: datetime, after_s: int = DEFAULT_STALE_AFTER_S) -> bool:
    """Has this scan been waiting on the scanner for longer than `after_s`?"""
    if scan.status not in PENDING_STATUSES:
        return False
    created = scan.created_at
    # Rows from Postgres are tz-aware; an in-memory fixture may not be. Treat a
    # naive timestamp as UTC rather than raising on the subtraction.
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    reference = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return (reference - created).total_seconds() > after_s


def settle_stale(
    scan: Scan, now: datetime | None = None, after_s: int = DEFAULT_STALE_AFTER_S
) -> Scan:
    """`scan`, or a failed copy of it if the scanner never came back.

    Returns the original object untouched when the scan is fine, so this is cheap
    to call on every row of a history list.
    """
    if not is_stale(scan, now or datetime.now(UTC), after_s):
        return scan
    return scan.model_copy(update={"status": "failed", "error": STALE_ERROR})
