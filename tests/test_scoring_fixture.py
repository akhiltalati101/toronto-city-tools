"""The frontend re-implements two small pieces of scoring so it can react
instantly without a request: city/scoring.apply_weights (weight sliders) and
ev/charger_access.score_from_walk_times (connector checkboxes). Both sides
are tested against tests/fixtures/scoring_cases.json — this test checks the
Python side, frontend/src/lib/scoring.test.ts the TypeScript side.

After an intentional scoring change, regenerate the fixture with:
    UPDATE_SCORING_FIXTURE=1 pytest tests/test_scoring_fixture.py
"""
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

from toronto_tools.city.scoring import PROFILES, CategoryScore, apply_weights
from toronto_tools.ev.charger_access import CONNECTOR_LABELS, score_from_walk_times

FIXTURE = Path(__file__).parent / "fixtures" / "scoring_cases.json"

BREAKDOWNS = [
    {"grocery": 100.0, "healthcare": 100.0, "parks": 100.0, "schools": 100.0, "transit": 100.0, "fitness": 100.0},
    {"grocery": 74.3, "healthcare": 45.1, "parks": 21.8, "schools": 0.0, "transit": 73.8, "fitness": 12.7},
    {"grocery": 90.0, "healthcare": 59.5, "parks": 72.8, "schools": 63.5, "transit": 100.0, "fitness": 92.0},
    {"grocery": 0.0, "healthcare": 0.0, "parks": 0.0, "schools": 0.0, "transit": 0.0, "fitness": 0.0},
    {"grocery": 50.05, "healthcare": 64.95, "parks": 35.0, "schools": 80.0, "transit": 49.95, "fitness": 65.0},
    {"grocery": 72.5, "healthcare": 0.0, "parks": 0.0, "schools": 0.0, "transit": 0.0, "fitness": 0.0},
    {"grocery": 72.7, "healthcare": 0.0, "parks": 0.0, "schools": 0.0, "transit": 0.0, "fitness": 0.0},
]
CUSTOM_WEIGHTS = [
    {"grocery": 0.05, "healthcare": 0.05, "parks": 0.6, "schools": 0.1, "transit": 0.15, "fitness": 0.05},
    # 72.5 * 0.5 = 36.25 exactly: Python's round() goes half-to-even (36.2),
    # JavaScript's toFixed/Math.round go up (36.3).
    {"grocery": 0.5, "healthcare": 0.5, "parks": 0.0, "schools": 0.0, "transit": 0.0, "fitness": 0.0},
]

WALK_TIMES = [
    [],
    [None, None],
    [120.0],
    [299.9, 600.0, None],
    [300.1],
    [450.0, 610.0, 700.0, 800.0],
    [899.0] * 12,
    [600.0, float("nan")],
    [15.0],    # nearest_min 0.25 -> 0.2 (half-to-even tie)
    [45.0],    # 0.75 -> 0.8
    [630.0],   # proximity exactly 45.0, combined 0.6*45 + 0.4*10 = 31.0
]


def _city_cases():
    cases = []
    for combined in BREAKDOWNS:
        breakdown = {cat: CategoryScore(0, 0, value, 0, None) for cat, value in combined.items()}
        for weights in [*PROFILES.values(), *CUSTOM_WEIGHTS]:
            result = apply_weights(breakdown, weights)
            cases.append({"combined": combined, "weights": weights, "overall": result.overall, "grade": result.grade})
    return cases


def _ev_cases():
    cases = []
    for walk_secs in WALK_TIMES:
        expected = asdict(score_from_walk_times(walk_secs))
        # JSON has no NaN; the frontend gets null for unreachable chargers.
        cases.append({"walk_secs": [None if t is None or math.isnan(t) else t for t in walk_secs], "expected": expected})
    return cases


def _build():
    return {
        "profiles": PROFILES,
        "connector_labels": CONNECTOR_LABELS,
        "city": _city_cases(),
        "ev": _ev_cases(),
    }


def test_scoring_fixture_matches_python():
    built = _build()
    if os.environ.get("UPDATE_SCORING_FIXTURE"):
        FIXTURE.write_text(json.dumps(built, indent=1) + "\n")
    assert json.loads(FIXTURE.read_text()) == json.loads(json.dumps(built)), (
        "Python scoring no longer matches tests/fixtures/scoring_cases.json — if the change is "
        "intentional, regenerate it (see module docstring) and update frontend/src/lib/scoring.ts to match."
    )
