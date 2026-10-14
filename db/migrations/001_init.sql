-- Antarctica initial schema (Postgres 16 + pgvector)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE sites (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  url         text NOT NULL UNIQUE,
  owner_note  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scans (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id      uuid REFERENCES sites(id),
  url          text NOT NULL,
  status       text NOT NULL DEFAULT 'queued'
               CHECK (status IN ('queued','running','done','failed')),
  attempts     int  NOT NULL DEFAULT 0,
  error        text,
  duration_ms  double precision,
  created_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz
);
CREATE INDEX scans_site_created ON scans (site_id, created_at DESC);

CREATE TABLE audits (
  scan_id            uuid PRIMARY KEY REFERENCES scans(id) ON DELETE CASCADE,
  lighthouse_version text,
  performance_score  int,
  fcp_ms             double precision,
  lcp_ms             double precision,
  tbt_ms             double precision,
  cls                double precision,
  speed_index_ms     double precision,
  raw                jsonb NOT NULL
);

CREATE TABLE findings (
  id             bigserial PRIMARY KEY,
  scan_id        uuid NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
  audit_id       text NOT NULL,
  title          text NOT NULL,
  description    text,
  score          double precision,
  savings_ms     double precision,
  savings_bytes  double precision
);
CREATE INDEX findings_scan ON findings (scan_id);

-- RAG corpus: web perf docs + past findings
CREATE TABLE doc_chunks (
  id         bigserial PRIMARY KEY,
  source     text NOT NULL CHECK (source IN ('doc','finding')),
  ref        text,                 -- URL or finding id
  content    text NOT NULL,
  embedding  vector(768) NOT NULL  -- Vertex text-embedding-005
);
CREATE INDEX doc_chunks_hnsw ON doc_chunks USING hnsw (embedding vector_cosine_ops);

-- AI fix proposals + per-step tracing
CREATE TABLE fix_proposals (
  id          bigserial PRIMARY KEY,
  finding_id  bigint NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  diagnosis   text,
  patch       text,
  confidence  double precision,
  iterations  int,
  tokens_in   int,
  tokens_out  int,
  latency_ms  double precision,
  cost_usd    numeric(10,6),
  accepted    boolean,             -- set by evals / human review
  created_at  timestamptz NOT NULL DEFAULT now()
);
