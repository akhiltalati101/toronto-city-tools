"""Filters the prebuilt city-wide amenities dataset (see citydata.py) down to
what's inside a given isochrone polygon, instead of querying Overpass live.
"""
import geopandas as gpd
from shapely.geometry import Polygon

from citydata import get_city_amenities

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

    Filters the citywide amenities dataset (loaded once via citydata.py) by
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


if __name__ == "__main__":
    from geocode import geocode_address
    from isochrone import compute_isochrone
    from network import load_network

    lat, lon = geocode_address("100 Queen St W")
    G = load_network(lat, lon, "walk")
    poly = compute_isochrone(G, lat, lon, "walk")

    print("Querying amenities within walk isochrone...")
    amenities = query_amenities(poly)

    for category, gdf in amenities.items():
        print(f"  {category:12s}: {len(gdf)} found")
