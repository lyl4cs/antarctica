/** Round score badge colored by Lighthouse band (90+ blue, 50-89 amber, <50 red). */
import { band } from "../lib/format";

export function ScoreChip({
  score,
  size = "md",
  label,
}: {
  score: number | null;
  size?: "xs" | "sm" | "md";
  /** Accessible label, e.g. "Score 54". Defaults to that. */
  label?: string;
}) {
  const tone = score === null ? "none" : band(score).tone;
  const cls = `score-chip ${size === "md" ? "" : size} tone-${tone}`;
  return (
    <span className={cls} aria-label={label ?? (score === null ? "No score" : `Score ${score}`)}>
      {score === null ? "—" : score}
    </span>
  );
}
