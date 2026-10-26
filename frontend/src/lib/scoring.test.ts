import { describe, expect, it } from "vitest";
import fixture from "../../../tests/fixtures/scoring_cases.json";
import { CONNECTOR_LABELS } from "./constants";
import { applyWeights, CATEGORIES, PROFILES, pyRound, scoreFromWalkTimes, type Weights } from "./scoring";

describe("matches the Python scoring (tests/fixtures/scoring_cases.json)", () => {
  it("has the same profiles and connector labels", () => {
    expect(PROFILES).toEqual(fixture.profiles);
    expect(CONNECTOR_LABELS).toEqual(fixture.connector_labels);
  });

  it.each(fixture.city.map((c, i) => [i, c] as const))("apply_weights case %i", (_, c) => {
    const breakdown = Object.fromEntries(CATEGORIES.map((cat) => [cat, { combined: c.combined[cat] }]));
    expect(applyWeights(breakdown, c.weights as Weights)).toEqual({ overall: c.overall, grade: c.grade });
  });

  it.each(fixture.ev.map((c, i) => [i, c] as const))("score_from_walk_times case %i", (_, c) => {
    expect(scoreFromWalkTimes(c.walk_secs)).toEqual(c.expected);
  });
});

describe("pyRound", () => {
  it("rounds exact ties half to even, like Python", () => {
    expect(pyRound(36.25)).toBe(36.2);
    expect(pyRound(36.35)).toBe(36.4); // 36.35 isn't an exact tie in binary: it's 36.350000000000001…
    expect(pyRound(0.25)).toBe(0.2);
    expect(pyRound(0.75)).toBe(0.8);
    expect(pyRound(0.15)).toBe(0.1); // 0.1499999…
    expect(pyRound(2.675, 2)).toBe(2.67); // the classic Python example
    expect(pyRound(100)).toBe(100);
    expect(pyRound(0)).toBe(0);
    // Whole-number display, like Python's f"{x:.0f}"
    expect(pyRound(36.5, 0)).toBe(36);
    expect(pyRound(37.5, 0)).toBe(38);
    expect(pyRound(37.46, 0)).toBe(37);
  });
});
