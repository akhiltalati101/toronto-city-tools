"""Filters the prebuilt city-wide amenities dataset (see data.py) down to
what's inside a given isochrone polygon, instead of querying Overpass live.
"""
import geopandas as gpd
from shapely.geometry import Polygon

from toronto_tools.city.data import get_city_amenities

CATEGORIES = {
    "grocery": {
        "shop": ["supermarket", "convenience", "greengrocer", "grocery"],
    },
    "healthcare": {
        "amenity": ["hospital", "clinic", "pharmacy", "doctors"],
    },
    "parks": {
        "leisure": ["park", "garden", "playground"],
    },
    "schools": {
        "amenity": ["school", "kindergarten", "college", "university"],
    },
    "transit": {
        "highway": ["bus_stop"],
        "railway": ["station", "subway_entrance", "tram_stop"],
        "amenity": ["bus_station"],
    },
    "fitness": {
        "leisure": ["fitness_centre", "swimming_pool", "sports_centre"],
    },
}


def query_amenities(polygon: Polygon) -> dict[str, gpd.GeoDataFrame]:
    """Return a dict of category → GeoDataFrame of amenities within the polygon.

    Filters the citywide amenities dataset (loaded once via data.py) by
    category, then by containment in the polygon using the category's
    spatial index rather than a full linear scan.
    """
    all_amenities = get_city_amenities()
    results = {}

    for category in CATEGORIES:
        gdf = all_amenities[all_amenities["category"] == category]
        if gdf.empty:
            results[category] = gdf
            continue
        idx = gdf.sindex.query(polygon, predicate="contains")
        results[category] = gdf.iloc[idx]

    return results
