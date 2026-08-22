"""Bundles the geocode -> network -> isochrone -> amenities -> score pipeline
into a single call, shared by the single-address and compare views in app.py.
"""
from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry import Polygon

from amenities import query_amenities
from geocode import geocode_address
from isochrone import compute_isochrone
from network import load_network
from scoring import ScoreResult, score_amenities


@dataclass
class ScorecardResult:
    address: str
    lat: float
    lon: float
    result: ScoreResult
    amenities: dict[str, gpd.GeoDataFrame]
    walk_polygon: Polygon
    bike_polygon: Polygon


def run_scorecard(address: str, weights: dict[str, float]) -> ScorecardResult:
    """Run the full scoring pipeline for a single address.

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from geocode_address).
    """
    lat, lon = geocode_address(address)

    G_walk = load_network(lat, lon, "walk")
    G_bike = load_network(lat, lon, "bike")

    walk_iso = compute_isochrone(G_walk, lat, lon, "walk")
    bike_iso = compute_isochrone(G_bike, lat, lon, "bike")

    amenities = query_amenities(walk_iso.polygon)
    result = score_amenities(amenities, G_walk, walk_iso.reachable, weights)

    return ScorecardResult(
        address=address,
        lat=lat,
        lon=lon,
        result=result,
        amenities=amenities,
        walk_polygon=walk_iso.polygon,
        bike_polygon=bike_iso.polygon,
    )
