// Ports of the two pieces of Python scoring the UI re-runs instantly, without
// a request: toronto_tools/city/scoring.py apply_weights (weight sliders) and
// toronto_tools/ev/charger_access.py score_from_walk_times (connector
// checkboxes). Both are checked against tests/fixtures/scoring_cases.json,
// which the Python tests also check — keep the arithmetic in the same order
// as the Python so floating point results match exactly.
import type { CategoryScore, ChargerAccess, Grade } from "./types";

export const CATEGORIES = ["grocery", "healthcare", "parks", "schools", "transit", "fitness"] as const;
export type Category = (typeof CATEGORIES)[number];
export type Weights = Record<Category, number>;

export const PROFILES: Record<string, Weights> = {
  General: { grocery: 0.2, healthcare: 0.2, parks: 0.15, schools: 0.15, transit: 0.2, fitness: 0.1 },
  Family: { grocery: 0.2, healthcare: 0.15, parks: 0.2, schools: 0.25, transit: 0.1, fitness: 0.1 },
  Senior: { grocery: 0.2, healthcare: 0.3, parks: 0.2, schools: 0.05, transit: 0.2, fitness: 0.05 },
  "Car-Free": { grocery: 0.2, healthcare: 0.15, parks: 0.1, schools: 0.1, transit: 0.35, fitness: 0.1 },
  Student: { grocery: 0.15, healthcare: 0.1, parks: 0.1, schools: 0.25, transit: 0.25, fitness: 0.15 },
};

/**
 * Python's round(x, digits): correctly rounded from the double's exact value,
 * with exact ties going to the even digit (round(36.25, 1) === 36.2, where
 * toFixed and Math.round both give 36.3).
 */
export function pyRound(x: number, digits = 1): number {
  // toFixed(30) is the exact decimal expansion far enough to tell a true tie
  // (…5000…) from a value merely displayed as one, for the 0–100 range here.
  const [intPart, frac] = Math.abs(x).toFixed(30).split(".");
  const tail = frac.slice(digits);
  if (tail[0] === "5" && /^0*$/.test(tail.slice(1))) {
    const kept = Number(`${intPart}.${frac.slice(0, digits)}`);
    const lastDigit = Number((intPart + frac.slice(0, digits)).slice(-1));
    const rounded = lastDigit % 2 === 0 ? kept : kept + 10 ** -digits;
    return Math.sign(x) * Number(rounded.toFixed(digits));
  }
  return Number(x.toFixed(digits));
}

export function grade(score: number): Grade {
  if (score >= 80) return "A";
  if (score >= 65) return "B";
  if (score >= 50) return "C";
  if (score >= 35) return "D";
  return "F";
}

export function applyWeights(breakdown: Record<string, Pick<CategoryScore, "combined">>, weights: Weights) {
  let total = 0;
  for (const cat of CATEGORIES) total += breakdown[cat].combined * weights[cat];
  const overall = pyRound(total, 1);
  return { overall, grade: grade(overall) };
}

const TRAVEL_TIME_MIN = 15;
const PROXIMITY_FULL_MARKS_MIN = 5;
const TARGET_CHARGER_COUNT = 10;
const PROXIMITY_WEIGHT = 0.6;
const VARIETY_WEIGHT = 0.4;

function proximityScore(nearestSec: number | null): number {
  if (nearestSec === null) return 0;
  const minutes = nearestSec / 60;
  if (minutes <= PROXIMITY_FULL_MARKS_MIN) return 100;
  const span = TRAVEL_TIME_MIN - PROXIMITY_FULL_MARKS_MIN;
  return Math.max(0, ((TRAVEL_TIME_MIN - minutes) / span) * 100);
}

/** One entry per charger: its walk time in seconds, or null if unreachable. */
export function scoreFromWalkTimes(walkSecs: (number | null)[]): ChargerAccess {
  const times = walkSecs.filter((t): t is number => t !== null && !Number.isNaN(t));
  const nearestSec = times.length ? Math.min(...times) : null;
  const prox = proximityScore(nearestSec);
  const variety = Math.min(walkSecs.length / TARGET_CHARGER_COUNT, 1) * 100;
  const combined = pyRound(PROXIMITY_WEIGHT * prox + VARIETY_WEIGHT * variety, 1);
  return {
    combined,
    proximity: pyRound(prox, 1),
    variety: pyRound(variety, 1),
    count: walkSecs.length,
    nearest_min: nearestSec !== null ? pyRound(nearestSec / 60, 1) : null,
    grade: grade(combined),
  };
}

/** Weights as whole percents (the slider values), and whether they total 100. */
export function toPercents(weights: Weights): Weights {
  return Object.fromEntries(CATEGORIES.map((c) => [c, Math.round(weights[c] * 100)])) as Weights;
}

export function fromPercents(percents: Weights): Weights {
  return Object.fromEntries(CATEGORIES.map((c) => [c, percents[c] / 100])) as Weights;
}

export function percentTotal(percents: Weights): number {
  return CATEGORIES.reduce((sum, c) => sum + percents[c], 0);
}
