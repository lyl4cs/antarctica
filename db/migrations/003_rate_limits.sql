-- Fixed-window rate-limit counters (see services/api/ratelimit.py, ADR 020).
-- One row per (key, window). key = e.g. 'scan:ip:1.2.3.4' or 'fix:global'.
CREATE TABLE rate_counters (
  key           text        NOT NULL,
  window_start  timestamptz NOT NULL,
  count         int         NOT NULL DEFAULT 0,
  PRIMARY KEY (key, window_start)
);
-- Old windows are pruned by time; this index makes that delete cheap.
CREATE INDEX rate_counters_window ON rate_counters (window_start);
