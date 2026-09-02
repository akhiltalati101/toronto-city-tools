"""Bundles the geocode -> home-charging-check -> public-charging-score
pipeline into a single call, shared by app.py.

v2: the public charging access score is always computed and shown — it
answers "how well is this location served by public charging," independent
of whether the resident personally has a driveway. Home charging feasibility
is checked in parallel and surfaced as supplementary "you may not need this"
info alongside install guidance, not as a gate that skips scoring. See
home_charging.py and charger_access.py for each step.
"""
from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry import Polygon

from charger_access import ChargerAccessResult, query_chargers_in_polygon, score_charger_access
from data import get_charging_stations
from geocode import geocode_address
from home_charging import HomeChargingResult, check_home_charging
from isochrone import compute_isochrone
from network import load_network


@dataclass
class ScorecardResult:
    address: str
    lat: float
    lon: float
    home_charging: HomeChargingResult
    charger_access: ChargerAccessResult
    isochrone_polygon: Polygon
    nearby_chargers: gpd.GeoDataFrame
    walk_graph: object   # networkx graph, kept so app.py can re-score by
                          # connector selection without recomputing the isochrone
    reachable: dict       # node_id -> travel time in seconds, from the isochrone


def run_scorecard(address: str) -> ScorecardResult:
    """Run the full v2 pipeline for a single address.

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from geocode_address).
    """
    lat, lon = geocode_address(address)
    home_result = check_home_charging(lat, lon)

    chargers_gdf = get_charging_stations()
    G = load_network(lat, lon)
    iso = compute_isochrone(G, lat, lon)
    nearby_chargers = query_chargers_in_polygon(chargers_gdf, iso.polygon)

    # Private/restricted-access stations are shown on the map (see mapview.py)
    # but shouldn't count toward the walkability score.
    public_chargers = nearby_chargers[nearby_chargers["access_code"] == "public"]
    access_result = score_charger_access(public_chargers, G, iso.reachable)

    return ScorecardResult(
        address=address, lat=lat, lon=lon,
        home_charging=home_result,
        charger_access=access_result, isochrone_polygon=iso.polygon, nearby_chargers=nearby_chargers,
        walk_graph=G, reachable=iso.reachable,
    )
