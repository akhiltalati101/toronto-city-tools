"""Downloads and holds prebuilt data used by the app:

- Charging stations: published to GitHub Releases by scripts/build_ev_data.py
  (rebuilt periodically by .github/workflows/rebuild-ev-data.yml).
- Walk network graph: reuses city-scorecard's own release rather than
  rebuilding an identical citywide walk graph here — EV charging access only
  needs the same street network city-scorecard already builds and publishes
  (see city-scorecard/scripts/build_city_data.py).

Each getter is st.cache_resource-wrapped so the download + load only happens
once per running app process, shared across all users' requests.
"""
import pickle
from pathlib import Path

import geopandas as gpd
import requests
import streamlit as st

EV_DATA_RELEASE_URL = (
    "https://github.com/akhiltalati101/toronto-city-tools/releases/download/ev-data"
)
CITY_DATA_RELEASE_URL = (
    "https://github.com/akhiltalati101/toronto-city-tools/releases/download/city-data"
)
CACHE_DIR = Path(__file__).resolve().parent / ".evdata_cache"

CHARGERS_ASSET = "toronto_chargers.geoparquet"
WALK_GRAPH_ASSET = "toronto_walk.graph.pkl"


def _download(base_url: str, asset_name: str) -> Path:
    dest = CACHE_DIR / asset_name
    if dest.exists():
        return dest

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{base_url}/{asset_name}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


@st.cache_resource(show_spinner="Loading charging station data (first request only)...")
def get_charging_stations() -> gpd.GeoDataFrame:
    """Return the prebuilt charging stations GeoDataFrame.

    Columns: geometry (point), address, network, level2_ports, level3_ports,
    total_ports.
    """
    path = _download(EV_DATA_RELEASE_URL, CHARGERS_ASSET)
    return gpd.read_parquet(path)


@st.cache_resource(show_spinner="Loading city walk network (first request only)...")
def get_walk_graph():
    """Return the prebuilt citywide walk-network graph."""
    path = _download(CITY_DATA_RELEASE_URL, WALK_GRAPH_ASSET)
    with open(path, "rb") as f:
        return pickle.load(f)
