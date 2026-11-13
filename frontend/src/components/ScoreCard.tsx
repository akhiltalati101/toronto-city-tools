import { GRADE_COLORS } from "../lib/constants";
import { pyRound } from "../lib/scoring";
import type { Grade } from "../lib/types";

export function GradeChip({ grade, large = false }: { grade: Grade; large?: boolean }) {
  return (
    <span
      className={`inline-block rounded-md font-bold ${large ? "px-4 py-1 text-xl" : "px-2 py-0.5 text-sm"}`}
      style={{ background: GRADE_COLORS[grade], color: grade === "A" || grade === "F" ? "#ffffff" : "#0b0b0b" }}
      aria-label={`Grade ${grade}`}
    >
      {grade}
    </span>
  );
}

/** Headline 0–100 score with its letter grade. */
export function ScoreCard({ score, grade, caption, className = "" }: { score: number; grade: Grade; caption: string; className?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl bg-surface-2 px-4 py-6 text-center ${className}`}>
      <div className="text-6xl font-extrabold leading-none text-ink" aria-label={`Score ${pyRound(score, 0)} out of 100`}>
        {pyRound(score, 0)}
      </div>
      <div className="mt-2 text-sm text-ink-2">{caption}</div>
      <div className="mt-3">
        <GradeChip grade={grade} large />
      </div>
    </div>
  );
}
