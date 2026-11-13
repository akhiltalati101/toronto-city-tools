"""Bundles the geocode -> network -> isochrone -> amenities -> score pipeline
into a single call, shared by the API's single-address and compare endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
from shapely.geometry import Polygon

from toronto_tools.city.amenities import query_amenities
from toronto_tools.city.data import get_city_graph
from toronto_tools.city.scoring import PROFILES, ScoreResult, score_amenities
from toronto_tools.common.geocode import resolve_location
from toronto_tools.common.isochrone import compute_isochrone

WALK_SPEED_KMH = 4.5
BIKE_SPEED_KMH = 15.0


@dataclass
class ScorecardResult:
    address: str
    lat: float
    lon: float
    result: ScoreResult
    amenities: dict[str, gpd.GeoDataFrame]
    walk_polygon: Polygon
    bike_polygon: Polygon


def run_scorecard(
    address: Optional[str],
    weights: Optional[dict[str, float]] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> ScorecardResult:
    """Run the full scoring pipeline for a single address, or for a map
    point if lat/lon are given.

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from resolve_location).
    """
    address, lat, lon = resolve_location(address, lat, lon)

    G_walk = get_city_graph("walk")
    G_bike = get_city_graph("bike")

    walk_iso = compute_isochrone(G_walk, lat, lon, WALK_SPEED_KMH)
    bike_iso = compute_isochrone(G_bike, lat, lon, BIKE_SPEED_KMH)

    amenities = query_amenities(walk_iso.polygon)
    result = score_amenities(amenities, G_walk, walk_iso.reachable, weights or PROFILES["General"])

    return ScorecardResult(
        address=address,
        lat=lat,
        lon=lon,
        result=result,
        amenities=amenities,
        walk_polygon=walk_iso.polygon,
        bike_polygon=bike_iso.polygon,
    )
