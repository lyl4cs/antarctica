/**
 * Home ("/"): URL form that starts a scan, plus the newest scans across all sites.
 *
 * HOW IT WORKS
 * Submitting POSTs /scans. The API answers 202 with the queued scan right away
 * (the slow Lighthouse run happens later in the scanner), so we immediately
 * navigate to /scans/:id, which polls until it finishes.
 * "Recent scans" is GET /scans?limit=6. A done scan links to its report; anything
 * else links to its scan page (which shows queued/running/failed).
 *
 * The iceberg on the right is decorative: its score and findings are fixed
 * illustration content from the design, not data, and are hidden from screen
 * readers apart from the SVG's description.
 */
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type ScanSummary } from "../api";
import { ArrowRightIcon, GlobeIcon, SpinnerIcon } from "../components/Icons";
import { HeroIceberg } from "../components/Illustrations";
import { ScoreChip } from "../components/ScoreChip";
import { Loading } from "../components/States";
import { displayUrl, formatRelativeDay, normalizeUrlInput } from "../lib/format";
import { useTitle } from "../lib/useTitle";

/** Shared by Home and the History search: validates, POSTs, then navigates. */
export function ScanForm({ initial = "" }: { initial?: string }) {
  const navigate = useNavigate();
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const url = normalizeUrlInput(value);
    if (!url) {
      setError("Enter a full web address, like https://yoursite.com");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const scan = await api.createScan(url);
      navigate(`/scans/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start the scan.");
      setBusy(false);
    }
  }

  return (
    <form className="scan-form" onSubmit={onSubmit} noValidate>
      <label htmlFor="scan-url">Website URL</label>
      <div className="scan-form-row">
        <div className="field">
          <GlobeIcon />
          <input
            id="scan-url"
            type="url"
            inputMode="url"
            autoComplete="url"
            placeholder="https://yoursite.com"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "scan-url-error scan-url-hint" : "scan-url-hint"}
          />
        </div>
        <button type="submit" className="pill" disabled={busy}>
          <span>{busy ? "Starting…" : "Scan site"}</span>
          <span className="pill-icon">{busy ? <SpinnerIcon /> : <ArrowRightIcon />}</span>
        </button>
      </div>
      {error && (
        <p className="form-error" id="scan-url-error" role="alert">
          {error}
        </p>
      )}
      <p className="form-hint" id="scan-url-hint">
        A scan takes about 30–60 seconds.
      </p>
    </form>
  );
}

function RecentScans() {
  const [items, setItems] = useState<ScanSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .listRecent(6, ctrl.signal)
      .then(setItems)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : "Couldn't load scans.");
      });
    return () => ctrl.abort();
  }, []);

  return (
    <section className="recent" aria-labelledby="recent-h">
      <div className="section-head">
        <h2 id="recent-h">Recent scans</h2>
        <Link to="/history">All history</Link>
      </div>
      {error ? (
        <p className="state state-error" role="alert">
          Couldn’t load recent scans. {error}
        </p>
      ) : items === null ? (
        <Loading label="Loading recent scans…" />
      ) : items.length === 0 ? (
        <p className="state">No scans yet. Your first one will show up here.</p>
      ) : (
        <ul className="recent-grid">
          {items.map(({ scan, performance_score }) => {
            const to = scan.status === "done" ? `/scans/${scan.id}/report` : `/scans/${scan.id}`;
            const statusText =
              scan.status === "done" ? undefined : scan.status === "failed" ? "Failed" : "In progress";
            return (
              <li key={scan.id}>
                <Link to={to} className="recent-row">
                  <span className="recent-meta">
                    <span className="recent-url">{displayUrl(scan.url)}</span>
                    <span className="recent-when">
                      {formatRelativeDay(new Date(scan.created_at))}
                      {statusText && ` · ${statusText}`}
                    </span>
                  </span>
                  <ScoreChip
                    score={scan.status === "done" ? performance_score : null}
                    label={scan.status === "done" ? undefined : statusText}
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function Home() {
  useTitle("");
  return (
    <>
      <main className="home-hero">
        <section className="home-copy">
          <div className="home-copy" style={{ gap: 20 }}>
            <h1>See the whole iceberg.</h1>
            <p className="home-lede">
              Antarctica measures how fast your page really loads, then writes a fix for every problem it
              finds, with the code and the docs to back it up.
            </p>
          </div>
          <ScanForm />
        </section>
        <figure className="hero-figure">
          <HeroIceberg />
          <div className="hero-score" aria-hidden="true">
            <span className="score-chip xs tone-mid">54</span>
            Your score
          </div>
          <div className="hero-findings" aria-hidden="true">
            <span className="label">Below the waterline</span>
            <div className="hero-finding">
              <b>Oversized hero image</b>
              <span className="mono">−1.9 s</span>
            </div>
            <div className="hero-finding">
              <b>Render-blocking CSS</b>
              <span className="mono">−1.2 s</span>
            </div>
            <div className="hero-finding">
              <b>Unused JavaScript</b>
              <span className="mono">−1.0 s</span>
            </div>
          </div>
        </figure>
      </main>
      <RecentScans />
    </>
  );
}
