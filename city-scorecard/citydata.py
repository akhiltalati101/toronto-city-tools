"""Downloads and holds the prebuilt city-wide network graphs and amenities
dataset published to GitHub Releases by scripts/build_city_data.py (rebuilt
periodically by .github/workflows/rebuild-city-data.yml).

network.py and amenities.py source their data from here instead of querying
Overpass live per address. Each getter is st.cache_resource-wrapped so the
download + load only happens once per running app process, shared across all
users' requests.
"""
import pickle
from pathlib import Path

import geopandas as gpd
import requests
import streamlit as st

RELEASE_ASSET_BASE_URL = (
    "https://github.com/akhiltalati101/toronto-city-tools/releases/download/city-data"
)
CACHE_DIR = Path(__file__).resolve().parent / ".citydata_cache"

ASSET_NAMES = {
    "walk": "toronto_walk.graph.pkl",
    "bike": "toronto_bike.graph.pkl",
    "amenities": "toronto_amenities.geoparquet",
}


def _download(asset_name: str) -> Path:
    dest = CACHE_DIR / asset_name
    if dest.exists():
        return dest

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{RELEASE_ASSET_BASE_URL}/{asset_name}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


@st.cache_resource(show_spinner="Loading city street network (first request only)...")
def get_city_graph(network_type: str):
    """Return the prebuilt city-wide walk or bike graph."""
    asset = ASSET_NAMES["bike"] if network_type == "bike" else ASSET_NAMES["walk"]
    path = _download(asset)
    with open(path, "rb") as f:
        return pickle.load(f)


@st.cache_resource(show_spinner="Loading city amenities data (first request only)...")
def get_city_amenities() -> gpd.GeoDataFrame:
    """Return the prebuilt city-wide amenities GeoDataFrame, with a 'category' column."""
    path = _download(ASSET_NAMES["amenities"])
    return gpd.read_parquet(path)
