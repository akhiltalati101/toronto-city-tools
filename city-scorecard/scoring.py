from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
import osmnx as ox

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
    nodes = ox.nearest_nodes(G, xs, ys)
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

    overall = round(sum(breakdown[cat].combined * weights[cat] for cat in breakdown), 1)
    return ScoreResult(overall=overall, breakdown=breakdown, weights=weights, grade=_grade(overall))


if __name__ == "__main__":
    from amenities import query_amenities
    from geocode import geocode_address
    from isochrone import compute_isochrone
    from network import load_network

    for address in ("100 Queen St W", "25 Rathburn Rd W, Etobicoke"):
        print(f"\n=== {address} ===")
        lat, lon = geocode_address(address)
        G = load_network(lat, lon, "walk")
        iso = compute_isochrone(G, lat, lon, "walk")
        amenities = query_amenities(iso.polygon)
        result = score_amenities(amenities, G, iso.reachable, PROFILES["General"])
        print(f"Overall: {result.overall:.1f} / 100  [{result.grade}]")
        print(f"{'Category':12s} {'Combined':>8} {'Proximity':>9} {'Variety':>7} {'Count':>5} {'Nearest':>7}")
        for cat, s in result.breakdown.items():
            nearest = f"{s.nearest_min}m" if s.nearest_min is not None else "—"
            print(f"{cat:12s} {s.combined:8.1f} {s.proximity:9.1f} {s.variety:7.1f} {s.count:5d} {nearest:>7}")
