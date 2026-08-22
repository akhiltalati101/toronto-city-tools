"""Downloads and holds the prebuilt charging-station and census-tract
datasets published to GitHub Releases by scripts/build_ev_data.py (rebuilt
periodically by .github/workflows/rebuild-ev-data.yml).

supply_demand.py sources its data from here instead of hitting the City of
Toronto Open Data / Statistics Canada APIs live per address. Each getter is
st.cache_resource-wrapped so the download + load only happens once per
running app process, shared across all users' requests.
"""
from pathlib import Path

import geopandas as gpd
import requests
import streamlit as st

RELEASE_ASSET_BASE_URL = (
    "https://github.com/akhiltalati101/toronto-city-tools/releases/download/ev-data"
)
CACHE_DIR = Path(__file__).resolve().parent / ".evdata_cache"

ASSET_NAMES = {
    "chargers": "toronto_chargers.geoparquet",
    "census_tracts": "toronto_census_tracts.geoparquet",
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


@st.cache_resource(show_spinner="Loading charging station data (first request only)...")
def get_charging_stations() -> gpd.GeoDataFrame:
    """Return the prebuilt charging stations GeoDataFrame.

    Columns: geometry (point), address, network, level2_ports, level3_ports,
    total_ports, ct_uid (the census tract it falls within).
    """
    path = _download(ASSET_NAMES["chargers"])
    return gpd.read_parquet(path)


@st.cache_resource(show_spinner="Loading census tract data (first request only)...")
def get_census_tracts() -> gpd.GeoDataFrame:
    """Return the prebuilt census tracts GeoDataFrame.

    Columns: geometry (polygon), ct_uid, population, median_household_income,
    income_percentile, port_count, local_ratio (ports per 1,000 residents),
    citywide_avg_ratio (same value repeated on every row, for convenience).
    """
    path = _download(ASSET_NAMES["census_tracts"])
    return gpd.read_parquet(path)
