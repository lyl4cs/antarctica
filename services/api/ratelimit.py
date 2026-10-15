"""Rate limiting: keep a public, unauthenticated API from being abused or bankrupted.

WHY
The API is public (anyone with the link) and two endpoints cost real money: a scan
runs Chrome on Cloud Run for ~30 s, and an AI fix is a Gemini call (~$0.0007 each,
up to 10 per request). One script in a loop could burn the whole budget. So:

- per visitor (by IP): a few scans and AI fixes per hour, plenty for a human;
- global (everyone together): a daily ceiling, so even many IPs can't run away.

HOW: FIXED WINDOWS IN POSTGRES
Time is cut into windows (e.g. each clock hour). For each (key, window) we keep a
counter row and do ONE atomic statement:
    INSERT ... ON CONFLICT (key, window_start) DO UPDATE SET count = count + cost
    RETURNING count
If the new count is over the limit we reject with HTTP 429 and a Retry-After
header (seconds until the window resets).

Why Postgres and not memory: Cloud Run runs up to 3 API instances; in-memory
counters would give each instance its own budget (3x the limit) and reset on every
cold start. Why not Redis: one more service to run and pay for; at this traffic a
single upsert on Neon is a few ms.

Tradeoff: fixed windows allow a burst at a boundary (e.g. 10 scans at 1:59 and 10
more at 2:00). A sliding window fixes that; not worth it at this scale.

WHICH IP
Cloud Run puts the caller's address LAST in X-Forwarded-For (anything before it was
supplied by the client and can be faked), so we take the last entry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Limits:
    scans_per_ip_per_hour: int
    scans_per_day: int
    fixes_per_ip_per_hour: int
    fixes_per_day: int

    @staticmethod
    def from_env() -> Limits:
        return Limits(
            scans_per_ip_per_hour=int(os.environ.get("RL_SCANS_PER_IP_HOUR", "10")),
            scans_per_day=int(os.environ.get("RL_SCANS_PER_DAY", "300")),
            fixes_per_ip_per_hour=int(os.environ.get("RL_FIXES_PER_IP_HOUR", "30")),
            fixes_per_day=int(os.environ.get("RL_FIXES_PER_DAY", "600")),
        )


HOUR, DAY = 3600, 86400


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    if parts:
        return parts[-1]
    return request.client.host if request.client else "unknown"


def window_start(now: datetime, seconds: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, UTC)


def enforce(store, key: str, limit: int, seconds: int, cost: int = 1,
            now: datetime | None = None, what: str = "requests") -> None:
    """Count `cost` against `key` in the current window; 429 if that exceeds `limit`."""
    now = now or datetime.now(UTC)
    start = window_start(now, seconds)
    count = store.hit(key, start, cost)
    if count > limit:
        retry = int((start.timestamp() + seconds) - now.timestamp()) + 1
        period = "hour" if seconds == HOUR else "day"
        raise HTTPException(
            status_code=429,
            detail=f"Too many {what}: the limit is {limit} per {period}. "
                   f"Try again in {retry // 60 + 1} min.",
            headers={"Retry-After": str(retry)},
        )
