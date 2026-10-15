/**
 * Scan page ("/scans/:id"): live status of one scan.
 *
 * HOW IT WORKS
 * 1. `useScanPolling` GETs /scans/{id} right away and then every 2 seconds while
 *    the scan is queued or running. It stops as soon as the scan is done or failed,
 *    and when you leave the page (the AbortController cancels any request in flight).
 * 2. queued/running/done render the ScanRunning design: the penguin sleeps while
 *    queued, wakes up while running, smiles when done. The elapsed timer is computed
 *    from the scan's created_at, so it is correct even if you reload mid-scan.
 * 3. When the scan is done we show the ready state for 1.5 s, then replace this
 *    history entry with the report (replace, so Back goes to where you came from
 *    instead of bouncing you forward again). The "Your Report Is Ready" button is
 *    there for anyone who doesn't want to wait.
 * 4. failed renders the ScanFailed design with the real error text and timings.
 *    Retry starts a NEW scan of the same URL (POST /scans) and moves to it.
 *
 * WHY POLLING (and not WebSockets / Server-Sent Events)
 * A scan takes 30-60 s and changes state about three times. Polling every 2 s is
 * ~30 tiny GETs, works through any proxy, needs nothing new on Cloud Run (which
 * bills per request-second, so a held-open socket per viewer would cost more), and
 * the API stays stateless. A push channel would be worth it for many fast updates,
 * not for three slow ones. See ADR 014.
 *
 * Network hiccups don't kill the page: a failed poll shows a small notice and the
 * next poll tries again. Only a 404 (unknown scan id) is final.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type Scan } from "../api";
import { ArrowDownIcon, CheckIcon, GlobeIcon, RetryIcon, SpinnerIcon } from "../components/Icons";
import { CrackedFloe, FloePenguin } from "../components/Illustrations";
import { ErrorState, Loading } from "../components/States";
import {
  displayUrl,
  formatClockSeconds,
  formatDuration,
  formatTime,
} from "../lib/format";
import { rememberScan } from "../lib/recentScans";
import { mood, steps, ticks, type Phase } from "../lib/scanProgress";
import { useTitle } from "../lib/useTitle";

export const POLL_MS = 2000;
export const READY_BEAT_MS = 1500;

function isActive(scan: Scan | null) {
  return !scan || scan.status === "queued" || scan.status === "running";
}

export function useScanPolling(id: string) {
  const [scan, setScan] = useState<Scan | null>(null);
  const [fatal, setFatal] = useState<ApiError | null>(null);
  const [hiccup, setHiccup] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setScan(null);
    setFatal(null);

    async function poll() {
      try {
        const s = await api.getScan(id, ctrl.signal);
        if (ctrl.signal.aborted) return;
        setScan(s);
        setHiccup(null);
        if (s.status === "queued" || s.status === "running") timer = setTimeout(poll, POLL_MS);
      } catch (e) {
        if (ctrl.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) {
          setFatal(e);
          return;
        }
        setHiccup(e instanceof Error ? e.message : "Connection problem.");
        timer = setTimeout(poll, POLL_MS); // transient: keep trying
      }
    }
    poll();
    return () => {
      ctrl.abort();
      clearTimeout(timer);
    };
  }, [id]);

  return { scan, fatal, hiccup };
}

/** Re-render on an interval while `active` (drives the elapsed timer). */
function useNow(active: boolean, everyMs = 500) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const iv = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(iv);
  }, [active, everyMs]);
  return now;
}

/** POST /scans for the same URL, then go to the new scan. Used by Retry / Scan again. */
export function useRescan() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function rescan(url: string) {
    setBusy(true);
    setError(null);
    try {
      const s = await api.createScan(url);
      rememberScan(s);
      navigate(`/scans/${s.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start a new scan.");
      setBusy(false);
    }
  }
  return { rescan, busy, error };
}

const COPY: Record<Phase, { title: (host: string) => string; chip: string; tone: string }> = {
  queued: { title: () => "Waiting for a scanner", chip: "Queued", tone: "queued" },
  running: { title: (host) => `Measuring ${host}`, chip: "Running", tone: "running" },
  ready: { title: () => "Done. Here’s what we found.", chip: "Done", tone: "done" },
};

function ArtChips({ url, chip, tone }: { url: string; chip: string; tone: string }) {
  return (
    <div className="scan-art-chips">
      <span className="url-chip">
        <GlobeIcon size={16} />
        <span>{displayUrl(url)}</span>
      </span>
      <span className={`chip status-chip tone-${tone}`}>
        <span className="status-dot" aria-hidden="true" />
        {chip}
      </span>
    </div>
  );
}

export function ScanProgressView({ scan, now, hiccup }: { scan: Scan; now: number; hiccup: string | null }) {
  const phase: Phase = scan.status === "done" ? "ready" : scan.status === "running" ? "running" : "queued";
  const created = new Date(scan.created_at);
  const finished = scan.finished_at ? new Date(scan.finished_at) : null;
  const elapsedS =
    phase === "queued"
      ? 0
      : Math.max(0, ((phase === "ready" && finished ? finished.getTime() : now) - created.getTime()) / 1000);
  const host = displayUrl(scan.url);
  const copy = COPY[phase];
  const sub =
    phase === "queued"
      ? "Your scan is in line and will start in a moment."
      : phase === "running"
        ? "Loading the page and timing every paint, script and layout shift. This usually takes 30–60 seconds."
        : `Finished in ${formatDuration(elapsedS * 1000)}: a score, five core metrics and the findings slowing the page down, each with an AI fix on request.`;

  return (
    <section className="scan-card" aria-labelledby="scan-title">
      <div className="scan-art">
        <FloePenguin mood={mood(phase)} />
        <ArtChips url={scan.url} chip={copy.chip} tone={copy.tone} />
      </div>
      <div className="scan-body">
        <div className="scan-heading" aria-live="polite">
          <h1 id="scan-title">{copy.title(host)}</h1>
          <p>{sub}</p>
        </div>

        <ol className="steps" aria-label="Scan progress">
          {steps(phase).map((s) => (
            <li className="step" key={s.label} aria-current={s.state === "current" ? "step" : undefined}>
              <div className="step-track">
                <span className={`step-dot ${s.state}`}>{s.state === "done" && <CheckIcon />}</span>
                <span className={`step-line${s.passed ? " passed" : ""}`} />
              </div>
              <span className={`step-label${s.state === "todo" ? "" : " active"}`}>
                {s.label}
                <span className="sr-only">
                  {s.state === "done" ? " (done)" : s.state === "current" ? " (in progress)" : ""}
                </span>
              </span>
            </li>
          ))}
        </ol>

        <div className="elapsed">
          <div className="elapsed-head">
            <span className="eyebrow">Elapsed</span>
            <span className="elapsed-value">{formatClockSeconds(elapsedS)}</span>
          </div>
          <div className="ticks" aria-hidden="true">
            <span className="ticks-zone" />
            {ticks(phase, elapsedS).map((t, i) => (
              <span key={i} className="tick" style={{ height: t.h, background: t.c }} />
            ))}
          </div>
          <div className="ticks-axis" aria-hidden="true">
            <span>0 s</span>
            <span>usually done between 30 and 60 s</span>
            <span>60 s</span>
          </div>
        </div>

        {hiccup && (
          <p className="scan-notice" role="status">
            Lost contact with the API ({hiccup}). Retrying…
          </p>
        )}

        <div className="scan-facts">
          {scan.attempts > 0 && (
            <span>
              Attempt <strong>{scan.attempts}</strong>
            </span>
          )}
          <span>
            Created <strong>{formatTime(created, true)}</strong>
          </span>
          {phase === "ready" && finished && (
            <span>
              Finished <strong>{formatTime(finished, true)}</strong>
            </span>
          )}
        </div>

        {phase === "ready" && (
          <div className="scan-ready">
            <Link to={`/scans/${scan.id}/report`} replace className="pill pill-lg">
              <span>Your Report Is Ready</span>
              <span className="pill-icon">
                <ArrowDownIcon />
              </span>
            </Link>
            <p>Opening it for you…</p>
          </div>
        )}
      </div>
    </section>
  );
}

export function ScanFailedView({ scan }: { scan: Scan }) {
  const { rescan, busy, error } = useRescan();
  const host = displayUrl(scan.url);
  const created = new Date(scan.created_at);
  const finished = scan.finished_at ? new Date(scan.finished_at) : null;
  const tried =
    scan.attempts > 1
      ? `We tried ${scan.attempts} times and couldn’t get a full load of ${host}.`
      : scan.attempts === 1
        ? `We tried once and couldn’t get a full load of ${host}.`
        : `The scan stopped before it could load ${host}.`;

  return (
    <section className="scan-card" aria-labelledby="scan-title">
      <div className="scan-art failed">
        <CrackedFloe />
        <ArtChips url={scan.url} chip="Failed" tone="poor" />
      </div>
      <div className="scan-body failed">
        <div className="scan-heading" aria-live="polite">
          <h1 id="scan-title">This scan didn’t finish</h1>
          <p>{tried}</p>
        </div>

        <div className="error-box">
          <span className="eyebrow">Error</span>
          <code>{scan.error || "No error message was recorded."}</code>
        </div>

        <dl className="facts">
          <div>
            <dt>Attempts</dt>
            <dd>{scan.attempts}</dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{formatTime(created)}</dd>
          </div>
          <div>
            <dt>Failed</dt>
            <dd>{finished ? formatTime(finished) : "—"}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{finished ? formatDuration(finished.getTime() - created.getTime()) : "—"}</dd>
          </div>
        </dl>

        <div className="checklist">
          <span>Before retrying, check that the page</span>
          <ul>
            <li>loads without signing in</li>
            <li>doesn’t block automated browsers</li>
            <li>starts responding within 45 seconds</li>
          </ul>
        </div>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="actions">
          <button type="button" className="pill pill-sand" onClick={() => rescan(scan.url)} disabled={busy}>
            <span>{busy ? "Starting…" : "Retry scan"}</span>
            <span className="pill-icon">{busy ? <SpinnerIcon /> : <RetryIcon />}</span>
          </button>
          <Link to="/" className="ghost">
            Scan a different URL
          </Link>
        </div>
      </div>
    </section>
  );
}

export function ScanPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { scan, fatal, hiccup } = useScanPolling(id);
  const now = useNow(isActive(scan));

  useTitle(scan ? `${scan.status === "failed" ? "Failed" : "Scanning"} ${displayUrl(scan.url)}` : "Scan");

  // Depend on id + status only: the timer starts once when the scan becomes done
  // (polls stop then, so nothing else re-triggers it) and is cancelled if we leave.
  const doneId = scan?.status === "done" ? scan.id : null;
  useEffect(() => {
    if (!doneId) return;
    const t = setTimeout(() => navigate(`/scans/${doneId}/report`, { replace: true }), READY_BEAT_MS);
    return () => clearTimeout(t);
  }, [doneId, navigate]);

  return (
    <main className="scan-main">
      {fatal ? (
        <div style={{ width: "100%", maxWidth: 760 }}>
          <ErrorState title="Scan not found" message={`There is no scan with id ${id}.`}>
            <Link to="/">Start a new scan</Link>
          </ErrorState>
        </div>
      ) : !scan ? (
        <div style={{ width: "100%", maxWidth: 760 }}>
          {hiccup ? (
            <ErrorState title="Can’t reach the API" message={`${hiccup} Retrying every 2 seconds…`} />
          ) : (
            <Loading label="Loading scan…" />
          )}
        </div>
      ) : scan.status === "failed" ? (
        <ScanFailedView scan={scan} />
      ) : (
        <ScanProgressView scan={scan} now={now} hiccup={hiccup} />
      )}
    </main>
  );
}
