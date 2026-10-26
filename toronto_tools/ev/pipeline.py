"""Bundles the geocode -> home-charging-check -> public-charging-score
pipeline into a single call, used by the API's /ev/score endpoint.

The public charging access score is always computed — it answers "how well
is this location served by public charging," independent of whether the
resident personally has a driveway. Home charging feasibility is checked
alongside and surfaced as supplementary "you may not need this" info, not as
a gate that skips scoring. See home_charging.py and charger_access.py.

Connector-type filtering happens client-side: each nearby charger is
returned with its walk time from the address, so the frontend can re-score
for any connector selection without another request (see
charger_access.score_from_walk_times, which the frontend mirrors).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
from shapely.geometry import Polygon

from toronto_tools.common.geocode import resolve_location
from toronto_tools.common.isochrone import compute_isochrone
from toronto_tools.ev.charger_access import (
    ChargerAccessResult, charger_walk_times, query_chargers_in_polygon, score_from_walk_times,
)
from toronto_tools.ev.data import get_charging_stations, get_walk_graph
from toronto_tools.ev.home_charging import HomeChargingResult, check_home_charging

WALK_SPEED_KMH = 4.5


@dataclass
class ScorecardResult:
    address: str
    lat: float
    lon: float
    home_charging: HomeChargingResult
    charger_access: ChargerAccessResult   # all public chargers, no connector filter
    isochrone_polygon: Polygon
    nearby_chargers: gpd.GeoDataFrame     # with a walk_sec column (None if unreachable)


def run_scorecard(address: Optional[str], lat: Optional[float] = None, lon: Optional[float] = None) -> ScorecardResult:
    """Run the full pipeline for a single address, or for a map point if
    lat/lon are given.

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from resolve_location).
    """
    address, lat, lon = resolve_location(address, lat, lon)
    home_result = check_home_charging(lat, lon)

    chargers_gdf = get_charging_stations()
    G = get_walk_graph()
    iso = compute_isochrone(G, lat, lon, WALK_SPEED_KMH)
    nearby_chargers = query_chargers_in_polygon(chargers_gdf, iso.polygon).copy()
    nearby_chargers["walk_sec"] = charger_walk_times(nearby_chargers, G, iso.reachable)

    # Private/restricted-access stations are shown on the map but shouldn't
    # count toward the walkability score.
    public_chargers = nearby_chargers[nearby_chargers["access_code"] == "public"]
    access_result = score_from_walk_times(public_chargers["walk_sec"].tolist())

    return ScorecardResult(
        address=address, lat=lat, lon=lon,
        home_charging=home_result,
        charger_access=access_result, isochrone_polygon=iso.polygon, nearby_chargers=nearby_chargers,
    )
