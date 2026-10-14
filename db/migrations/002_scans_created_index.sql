-- GET /scans (home page "Recent scans") orders ALL scans by created_at, newest first.
-- 001 only indexes (site_id, created_at), which can't serve a global ORDER BY, so
-- without this Postgres reads the whole table and sorts it on every page load.
-- With it, "newest 20" is a short walk down the index.
CREATE INDEX IF NOT EXISTS scans_created ON scans (created_at DESC);
