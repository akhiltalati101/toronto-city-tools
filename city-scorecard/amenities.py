import warnings

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Polygon

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

    Polygon and railway/area features are reduced to their centroid so every
    result is a point, making distance and containment checks uniform.
    """
    results = {}

    for category, tags in CATEGORIES.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gdf = ox.features_from_polygon(polygon, tags=tags)
        except Exception:
            # No features found returns an empty GeoDataFrame
            gdf = gpd.GeoDataFrame(geometry=[])

        if not gdf.empty:
            # Project to UTM for accurate centroid, then back to WGS84
            gdf = gdf.copy()
            utm = gdf.estimate_utm_crs()
            gdf["geometry"] = gdf.to_crs(utm).geometry.centroid
            gdf = gdf.set_crs(utm).to_crs("EPSG:4326")
            # Keep only points that fall inside the polygon
            gdf = gdf[gdf.within(polygon)]

        results[category] = gdf

    return results


if __name__ == "__main__":
    from geocode import geocode_address
    from isochrone import compute_isochrone
    from network import load_network

    lat, lon = geocode_address("100 Queen St W")
    G = load_network(lat, lon, "walk")
    poly = compute_isochrone(G, lat, lon, "walk")

    print(f"Querying amenities within walk isochrone...")
    amenities = query_amenities(poly)

    for category, gdf in amenities.items():
        print(f"  {category:12s}: {len(gdf)} found")
