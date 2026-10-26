"""Holds the prebuilt city-wide network graphs and amenities dataset
published to GitHub Releases by scripts/build_city_data.py (rebuilt
periodically by .github/workflows/rebuild-city-data.yml).

amenities.py and pipeline.py source their data from here instead of querying
Overpass live per address. Each getter is lru_cache-wrapped so the download
+ load only happens once per process, shared across all requests. The walk
graph is also what ev/pipeline.py routes over, so both tools share one copy
in memory.
"""
import pickle
from functools import lru_cache

import geopandas as gpd

from toronto_tools.common.release_data import download

RELEASE_TAG = "city-data"

ASSET_NAMES = {
    "walk": "toronto_walk.graph.pkl",
    "bike": "toronto_bike.graph.pkl",
    "amenities": "toronto_amenities.geoparquet",
}


@lru_cache(maxsize=None)
def get_city_graph(network_type: str):
    """Return the prebuilt city-wide walk or bike graph."""
    asset = ASSET_NAMES["bike"] if network_type == "bike" else ASSET_NAMES["walk"]
    with open(download(RELEASE_TAG, asset), "rb") as f:
        return pickle.load(f)


@lru_cache(maxsize=None)
def get_city_amenities() -> gpd.GeoDataFrame:
    """Return the prebuilt city-wide amenities GeoDataFrame, with a 'category' column."""
    return gpd.read_parquet(download(RELEASE_TAG, ASSET_NAMES["amenities"]))
