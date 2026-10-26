from dataclasses import dataclass
from typing import Optional

import geopandas as gpd

from toronto_tools.common.nearest import nearest_nodes

# Count needed to earn full variety marks per category
TARGETS: dict[str, int] = {
    "grocery":    8,
    "healthcare": 6,
    "parks":      50,
    "schools":    8,
    "transit":    40,
    "fitness":    5,
}

# Preset profiles: category → weight (must sum to 1.0)
PROFILES: dict[str, dict[str, float]] = {
    "General": {
        "grocery": 0.20, "healthcare": 0.20, "parks": 0.15,
        "schools": 0.15, "transit": 0.20, "fitness": 0.10,
    },
    "Family": {
        "grocery": 0.20, "healthcare": 0.15, "parks": 0.20,
        "schools": 0.25, "transit": 0.10, "fitness": 0.10,
    },
    "Senior": {
        "grocery": 0.20, "healthcare": 0.30, "parks": 0.20,
        "schools": 0.05, "transit": 0.20, "fitness": 0.05,
    },
    "Car-Free": {
        "grocery": 0.20, "healthcare": 0.15, "parks": 0.10,
        "schools": 0.10, "transit": 0.35, "fitness": 0.10,
    },
    "Student": {
        "grocery": 0.15, "healthcare": 0.10, "parks": 0.10,
        "schools": 0.25, "transit": 0.25, "fitness": 0.15,
    },
}

PROXIMITY_WEIGHT = 0.6
VARIETY_WEIGHT = 0.4


@dataclass
class CategoryScore:
    proximity: float   # 0–100, based on distance to nearest amenity
    variety: float     # 0–100, based on count vs target
    combined: float    # weighted blend
    count: int
    nearest_min: Optional[float]   # travel time in minutes to nearest amenity


@dataclass
class ScoreResult:
    overall: float
    breakdown: dict[str, CategoryScore]
    weights: dict[str, float]
    grade: str


def _grade(score: float) -> str:
    if score >= 80: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"


def _proximity_score(nearest_sec: Optional[float]) -> float:
    if nearest_sec is None:
        return 0.0
    minutes = nearest_sec / 60
    if minutes <= 5:
        return 100.0
    return max(0.0, (15 - minutes) / 10 * 100)


def _variety_score(count: int, target: int) -> float:
    return min(count / target, 1.0) * 100


def _nearest_travel_time(
    gdf: gpd.GeoDataFrame, G, reachable: dict
) -> Optional[float]:
    if gdf.empty:
        return None
    xs = gdf.geometry.x.tolist()
    ys = gdf.geometry.y.tolist()
    nodes = nearest_nodes(G, xs, ys)
    times = [reachable[n] for n in nodes if n in reachable]
    return min(times) if times else None


def score_amenities(
    amenities: dict[str, gpd.GeoDataFrame],
    G,
    reachable: dict,
    weights: dict[str, float],
) -> ScoreResult:
    breakdown = {}
    for cat, gdf in amenities.items():
        nearest_sec = _nearest_travel_time(gdf, G, reachable)
        prox = _proximity_score(nearest_sec)
        var = _variety_score(len(gdf), TARGETS[cat])
        combined = round(PROXIMITY_WEIGHT * prox + VARIETY_WEIGHT * var, 1)
        breakdown[cat] = CategoryScore(
            proximity=round(prox, 1),
            variety=round(var, 1),
            combined=combined,
            count=len(gdf),
            nearest_min=round(nearest_sec / 60, 1) if nearest_sec is not None else None,
        )

    return apply_weights(breakdown, weights)


def apply_weights(breakdown: dict[str, CategoryScore], weights: dict[str, float]) -> ScoreResult:
    """Combine per-category scores into an overall score. The breakdown doesn't
    depend on weights, so the app re-runs just this when sliders move instead
    of re-running the whole pipeline."""
    overall = round(sum(s.combined * weights[cat] for cat, s in breakdown.items()), 1)
    return ScoreResult(overall=overall, breakdown=breakdown, weights=weights, grade=_grade(overall))
