"""Holds prebuilt data used by the EV tool:

- Charging stations: NREL Alternative Fuel Stations API data (public and
  private-access, GTA-wide), published to GitHub Releases by
  scripts/build_ev_data.py (rebuilt periodically by
  .github/workflows/rebuild-ev-data.yml). See access_code on each row —
  scoring should filter to "public" (see charger_access.py); the tool itself
  still only accepts addresses within Toronto (see common/geocode.py).
- Walk network graph: reuses the city tool's graph (city/data.py) rather
  than a second identical citywide walk graph.
"""
import threading
from functools import lru_cache

import geopandas as gpd

from toronto_tools.city.data import get_city_graph
from toronto_tools.common.release_data import download

RELEASE_TAG = "ev-data"
CHARGERS_ASSET = "toronto_chargers.geoparquet"


_load_lock = threading.Lock()


@lru_cache(maxsize=None)
def _load_charging_stations() -> gpd.GeoDataFrame:
    return gpd.read_parquet(download(RELEASE_TAG, CHARGERS_ASSET))


def get_charging_stations() -> gpd.GeoDataFrame:
    """Return the prebuilt charging stations GeoDataFrame.

    Columns: geometry (point), address, network, level2_ports, level3_ports,
    total_ports, access_code ("public"/"private"/"unknown"), connector_types
    (comma-joined, e.g. "J1772, CHADEMO"), pricing, access_hours (the latter
    two are free text from NREL, "Not listed" when the network doesn't
    report them).
    """
    with _load_lock:
        return _load_charging_stations()


def get_walk_graph():
    """Return the prebuilt citywide walk-network graph (shared with city/)."""
    return get_city_graph("walk")
