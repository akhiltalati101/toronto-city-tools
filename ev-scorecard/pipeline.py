"""Bundles the geocode -> home-charging-check -> (public charging fallback)
pipeline into a single call, shared by app.py.

v1's question is "should I own an EV at this address": check home charging
first; only fall back to scoring public charging access if home charging
isn't feasible. See home_charging.py and charger_access.py for each step.
"""
from dataclasses import dataclass
from typing import Optional

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
    charger_access: Optional[ChargerAccessResult]      # None when home charging is feasible
    isochrone_polygon: Optional[Polygon]                # None when home charging is feasible
    nearby_chargers: Optional[gpd.GeoDataFrame]         # None when home charging is feasible


def run_scorecard(address: str) -> ScorecardResult:
    """Run the full v1 pipeline for a single address.

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from geocode_address).
    """
    lat, lon = geocode_address(address)
    home_result = check_home_charging(lat, lon)

    if home_result.feasible:
        return ScorecardResult(
            address=address, lat=lat, lon=lon,
            home_charging=home_result,
            charger_access=None, isochrone_polygon=None, nearby_chargers=None,
        )

    chargers_gdf = get_charging_stations()
    G = load_network(lat, lon)
    iso = compute_isochrone(G, lat, lon)
    nearby_chargers = query_chargers_in_polygon(chargers_gdf, iso.polygon)
    access_result = score_charger_access(nearby_chargers, G, iso.reachable)

    return ScorecardResult(
        address=address, lat=lat, lon=lon,
        home_charging=home_result,
        charger_access=access_result, isochrone_polygon=iso.polygon, nearby_chargers=nearby_chargers,
    )
