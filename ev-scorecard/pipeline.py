"""Bundles the geocode -> locate tract -> score pipeline into a single call,
shared by the single-address and compare views in app.py.
"""
from dataclasses import dataclass

import geopandas as gpd

from data import get_census_tracts, get_charging_stations
from geocode import geocode_address
from supply_demand import SupplyResult, compute_supply_index


@dataclass
class ScorecardResult:
    address: str
    lat: float
    lon: float
    result: SupplyResult
    tract_geometry: object            # shapely Polygon for the containing census tract
    nearby_chargers: gpd.GeoDataFrame  # chargers within the containing tract


def run_scorecard(address: str, k: float = 1.0) -> ScorecardResult:
    """Run the full EV supply/demand pipeline for a single address.

    Raises ValueError if the address can't be geocoded, falls outside the
    supported Toronto area, or doesn't fall within any known census tract.
    """
    lat, lon = geocode_address(address)

    ct_gdf = get_census_tracts()
    chargers_gdf = get_charging_stations()

    result = compute_supply_index(lat, lon, ct_gdf, chargers_gdf, k=k)

    tract_row = ct_gdf[ct_gdf["ct_uid"] == result.ct_uid].iloc[0]
    nearby_chargers = chargers_gdf[chargers_gdf["ct_uid"] == result.ct_uid]

    return ScorecardResult(
        address=address,
        lat=lat,
        lon=lon,
        result=result,
        tract_geometry=tract_row.geometry,
        nearby_chargers=nearby_chargers,
    )
