-- The conditions a score was measured under (see services/scanner/parse.py, ADR 022).
--
-- A Lighthouse score only means something relative to the device, network and CPU
-- throttling it was measured under, and to the Lighthouse version that weighted the
-- metrics. Without these, the history chart and the two-scan diff can present a
-- config change as a real improvement.
--
-- Columns, not a jsonb blob: the metrics next to them are columns too, and the
-- history list reads these per scan. Extracting from audits.raw on every read would
-- detoast a ~500 KB document per row.
--
-- All nullable: scans recorded before this migration keep their rows and simply
-- report unknown conditions, which the UI handles.
ALTER TABLE audits
  ADD COLUMN form_factor       text,              -- "mobile" | "desktop"
  ADD COLUMN throttling_method text,              -- "simulate" | "devtools" | "provided"
  ADD COLUMN cpu_slowdown      double precision,  -- multiplier, e.g. 4
  ADD COLUMN rtt_ms            double precision,  -- simulated round-trip time
  ADD COLUMN throughput_kbps   double precision,  -- simulated download throughput
  ADD COLUMN benchmark_index   double precision;  -- host machine speed, not the site's
