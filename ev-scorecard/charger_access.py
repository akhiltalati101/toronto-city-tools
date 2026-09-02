"""Scores public EV charging access within a 15-minute walk of an address —
always computed and shown, independent of home-charging feasibility (see
home_charging.py, which is now a separate supplementary check).

Mirrors city-scorecard's proximity(60%)/variety(40%) scoring formula
(scoring.py), applied to a single category — public EV chargers — instead of
its six amenity categories. Deliberately doesn't weigh this against local
EV-ownership demand; it only answers "is there charging nearby," not "is that
charging already saturated."
"""
from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Polygon

from isochrone import TRAVEL_TIME_MIN

# Chargers reachable within a 15-min walk needed for full "variety" marks.
# Recalibrated 2026-08 against the NREL-scale dataset (~1,070 public
# stations in Toronto): a spot-check of 8 addresses across downtown,
# midtown, North York, Scarborough, Etobicoke, and the east/west ends found
# counts of [1, 2, 2, 13, 15, 23, 51, 107] (median 14) — the old value of 3
# saturated variety almost everywhere except the most charger-poor suburbs
# (e.g. Scarborough Town Centre and North Toronto both had just 1-2). 10
# sits below the median so genuinely well-served areas still cap at 100,
# while charger-poor suburbs (1-2 stations) stay clearly differentiated.
# See docs/algorithm_audit.md for the full methodology and sample.
#
# Calibrated against *all* public chargers combined — once scoring is
# filtered to a single connector type (see filter_by_connectors below), a
# lower count is expected and correct, not a sign this needs re-tuning: a
# CHAdeMO-only driver genuinely has fewer usable stations than "any public
# charger" would suggest.
TARGET_CHARGER_COUNT = 10

# Connector codes worth surfacing as a compatibility filter, in display
# order, mapped to a rider-friendly label. Codes match NREL's
# ev_connector_types values (see connector_types column, build_ev_data.py).
# NEMA515 (a standard household outlet) is deliberately excluded — it's on
# only 2 stations in the current dataset and virtually every EV can already
# use one via its included adapter, so it isn't a meaningful filter.
CONNECTOR_LABELS = {
    "J1772": "J1772 (standard Level 2)",
    "J1772COMBO": "CCS / J1772 Combo (DC fast)",
    "CHADEMO": "CHAdeMO (DC fast)",
    "TESLA": "Tesla (NACS / J3400)",
}

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


_PROXIMITY_FULL_MARKS_MIN = 5  # walk time at/under which proximity maxes out


def _proximity_score(nearest_sec: Optional[float]) -> float:
    if nearest_sec is None:
        return 0.0
    minutes = nearest_sec / 60
    if minutes <= _PROXIMITY_FULL_MARKS_MIN:
        return 100.0
    span = TRAVEL_TIME_MIN - _PROXIMITY_FULL_MARKS_MIN
    return max(0.0, (TRAVEL_TIME_MIN - minutes) / span * 100)


def _variety_score(count: int) -> float:
    return min(count / TARGET_CHARGER_COUNT, 1.0) * 100


def query_chargers_in_polygon(chargers_gdf: gpd.GeoDataFrame, polygon: Polygon) -> gpd.GeoDataFrame:
    if chargers_gdf.empty:
        return chargers_gdf
    idx = chargers_gdf.sindex.query(polygon, predicate="contains")
    return chargers_gdf.iloc[idx]


def parse_connector_types(value) -> set[str]:
    """Split a charger's comma-joined connector_types value (e.g.
    "CHADEMO, J1772COMBO") into a set of codes. Handles None/NaN/"Not
    listed" by returning an empty set, so such a charger never matches any
    selection."""
    if not value or not isinstance(value, str) or value == "Not listed":
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def filter_by_connectors(chargers_gdf: gpd.GeoDataFrame, selected: set[str]) -> gpd.GeoDataFrame:
    """Keep only chargers compatible with at least one connector in
    `selected`. An empty `selected` (nothing chosen yet) returns an empty
    frame — score_charger_access already scores that as 0/F, so "no
    connector picked" and "no compatible charger nearby" share one path."""
    if not selected or chargers_gdf.empty:
        return chargers_gdf.iloc[0:0]
    mask = chargers_gdf["connector_types"].apply(lambda v: bool(parse_connector_types(v) & selected))
    return chargers_gdf[mask]


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
