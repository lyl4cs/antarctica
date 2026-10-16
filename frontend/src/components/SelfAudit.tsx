/**
 * The self-audit showcase: sn0wy's own site, scanned round after round.
 *
 * HOW IT WORKS
 * `CASE_STUDY.steps` (examples.ts) carries only the story: which scan, in what
 * order, what changed. Every score and date shown here is looked up from the
 * `history` the page already loaded from GET /sites/scans, so the component cannot
 * display a number the API does not currently report. A step whose scan is missing
 * from that history renders as unknown rather than as a score, and a step with no
 * `scanId` renders as pending work.
 *
 * WHY NOT STORE THE SCORES
 * A hardcoded "88 → 96" is unverifiable and rots silently: re-run a scan, or drop
 * one, and the page keeps asserting the old number. Reading them live means the
 * worst failure is an honest "—". For a page whose entire job is to be evidence
 * that the tool works, that trade is the whole point.
 *
 * WHY NO EXTRA REQUEST
 * `history` is already in hand on this page, so the showcase costs nothing. Fetching
 * each step's full report would add N requests to render numbers that are already
 * written down in `evidence`, which describes a past scan and therefore cannot drift.
 */
import { Link } from "react-router-dom";
import { CASE_STUDY, REPO_URL, type CaseStudyStep } from "../examples";
import type { ScanSummary } from "../api";
import { formatShortDate, formatTime, scoreDelta } from "../lib/format";

/** A step joined to whatever the live history knows about its scan. */
interface ResolvedStep {
  step: CaseStudyStep;
  score: number | null;
  /** null when the scan is not in this site's history (or there is no scanId). */
  summary: ScanSummary | null;
}

export function resolveSteps(
  steps: CaseStudyStep[],
  history: ScanSummary[],
): ResolvedStep[] {
  const byId = new Map(history.map((h) => [h.scan.id, h]));
  return steps.map((step) => {
    const summary = step.scanId ? (byId.get(step.scanId) ?? null) : null;
    return { step, summary, score: summary?.performance_score ?? null };
  });
}

function StepScore({ score, previous }: { score: number | null; previous: number | null }) {
  if (score === null) {
    return (
      <span className="selfaudit-score is-pending" aria-label="not measured yet">
        —
      </span>
    );
  }
  const delta = previous !== null ? scoreDelta(previous, score) : null;
  return (
    <span className="selfaudit-score">
      <b>{score}</b>
      {delta && delta.direction !== "same" && (
        <span className={`selfaudit-delta ${delta.direction === "better" ? "up" : "down"}`}>
          {delta.label}
        </span>
      )}
    </span>
  );
}

export function SelfAudit({ history }: { history: ScanSummary[] }) {
  const resolved = resolveSteps(CASE_STUDY.steps, history);
  // Scores of the steps that really have one, so a pending step in the middle does
  // not break the delta chain between the two measured scans either side of it.
  let previous: number | null = null;

  return (
    <section className="selfaudit" aria-labelledby="selfaudit-h">
      <div className="section-head">
        <h2 id="selfaudit-h">Built with sn0wy, and audited by it</h2>
      </div>
      <p className="selfaudit-intro">{CASE_STUDY.note}</p>

      <ol className="selfaudit-steps">
        {resolved.map(({ step, score, summary }, i) => {
          const prev = previous;
          if (score !== null) previous = score;
          const pending = !step.scanId;
          return (
            <li
              key={step.scanId || `pending-${i}`}
              className={`selfaudit-step${pending ? " is-pending" : ""}`}
            >
              <div className="selfaudit-marker" aria-hidden="true">
                <span className="selfaudit-dot" />
              </div>

              <div className="selfaudit-body">
                <div className="selfaudit-head">
                  <StepScore score={score} previous={prev} />
                  <div className="selfaudit-titles">
                    <h3>{step.title}</h3>
                    <p className="selfaudit-when">
                      {summary
                        ? `${formatShortDate(new Date(summary.scan.created_at))} · ${formatTime(new Date(summary.scan.created_at))}`
                        : pending
                          ? "Not deployed yet"
                          : "Scan no longer available"}
                    </p>
                  </div>
                </div>

                <p className="selfaudit-detail">{step.detail}</p>

                {step.evidence && step.evidence.length > 0 && (
                  <ul className="selfaudit-evidence">
                    {step.evidence.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}

                <p className="selfaudit-links">
                  {summary && (
                    <Link to={`/scans/${summary.scan.id}/report`}>See this report</Link>
                  )}
                  {step.prs?.map((n) => (
                    <a
                      key={n}
                      href={`${REPO_URL}/pull/${n}`}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      PR #{n}
                    </a>
                  ))}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
