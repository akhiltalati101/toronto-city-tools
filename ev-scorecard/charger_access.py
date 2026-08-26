"""Scores public EV charging access within a 15-minute walk of an address —
the fallback shown when home charging isn't available (see home_charging.py).

Mirrors city-scorecard's proximity(60%)/variety(40%) scoring formula
(scoring.py), applied to a single category — public EV chargers — instead of
its six amenity categories. v1 deliberately doesn't weigh this against local
EV-ownership demand; it only answers "is there charging nearby," not "is that
charging already saturated."
"""
from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Polygon

# Chargers reachable within a 15-min walk needed for full "variety" marks.
# TODO: was calibrated for ~80 city-operated stations citywide; the NREL
# swap (all public networks — ChargePoint, FLO, etc.) puts ~1,070 public
# stations in Toronto alone, so dense areas will now trivially max out
# variety at 3. Revisit this threshold before relying on the variety score
# to differentiate walkable access city-wide.
TARGET_CHARGER_COUNT = 3

PROXIMITY_WEIGHT = 0.6
VARIETY_WEIGHT = 0.4

GRADE_COLORS = {"A": "#2e7d32", "B": "#66bb6a", "C": "#fbc02d", "D": "#fb8c00", "F": "#e53935"}


@dataclass
class ChargerAccessResult:
    combined: float
    proximity: float
    variety: float
    count: int
    nearest_min: Optional[float]
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


def _variety_score(count: int) -> float:
    return min(count / TARGET_CHARGER_COUNT, 1.0) * 100


def query_chargers_in_polygon(chargers_gdf: gpd.GeoDataFrame, polygon: Polygon) -> gpd.GeoDataFrame:
    if chargers_gdf.empty:
        return chargers_gdf
    idx = chargers_gdf.sindex.query(polygon, predicate="contains")
    return chargers_gdf.iloc[idx]


def score_charger_access(chargers_gdf: gpd.GeoDataFrame, G, reachable: dict) -> ChargerAccessResult:
    if chargers_gdf.empty:
        nearest_sec = None
    else:
        xs = chargers_gdf.geometry.x.tolist()
        ys = chargers_gdf.geometry.y.tolist()
        nodes = ox.nearest_nodes(G, xs, ys)
        times = [reachable[n] for n in nodes if n in reachable]
        nearest_sec = min(times) if times else None

    prox = _proximity_score(nearest_sec)
    var = _variety_score(len(chargers_gdf))
    combined = round(PROXIMITY_WEIGHT * prox + VARIETY_WEIGHT * var, 1)

    return ChargerAccessResult(
        combined=combined,
        proximity=round(prox, 1),
        variety=round(var, 1),
        count=len(chargers_gdf),
        nearest_min=round(nearest_sec / 60, 1) if nearest_sec is not None else None,
        grade=_grade(combined),
    )


if __name__ == "__main__":
    from data import get_charging_stations
    from geocode import geocode_address
    from isochrone import compute_isochrone
    from network import load_network

    chargers_gdf = get_charging_stations()
    for address in ("100 Queen St W", "25 Rathburn Rd W, Etobicoke"):
        print(f"\n=== {address} ===")
        lat, lon = geocode_address(address)
        G = load_network(lat, lon)
        iso = compute_isochrone(G, lat, lon)
        nearby = query_chargers_in_polygon(chargers_gdf, iso.polygon)
        public_nearby = nearby[nearby["access_code"] == "public"]
        result = score_charger_access(public_nearby, G, iso.reachable)
        print(f"Grade {result.grade} ({result.combined}/100) — {result.count} chargers, nearest {result.nearest_min} min")
