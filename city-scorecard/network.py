import os
import pickle

import osmnx as ox

CACHE_DIR = ".cache/networks"
WALK_DIST_M = 1125   # 15 min @ 4.5 km/h
BIKE_DIST_M = 3750   # 15 min @ 15 km/h


def _cache_path(lat: float, lon: float, network_type: str) -> str:
    return os.path.join(CACHE_DIR, f"{lat:.4f}_{lon:.4f}_{network_type}.pkl")


def load_network(lat: float, lon: float, network_type: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(lat, lon, network_type)

    if os.path.exists(path):
        print(f"  [cache] loading {network_type} network from disk")
        with open(path, "rb") as f:
            return pickle.load(f)

    dist = BIKE_DIST_M if network_type == "bike" else WALK_DIST_M
    print(f"  [osmnx] downloading {network_type} network ({dist}m radius)...")
    G = ox.graph_from_point((lat, lon), dist=dist, network_type=network_type)

    with open(path, "wb") as f:
        pickle.dump(G, f)

    return G


if __name__ == "__main__":
    from geocode import geocode_address

    lat, lon = geocode_address("100 Queen St W")
    print(f"Coordinate: ({lat:.5f}, {lon:.5f})")

    for ntype in ("walk", "bike"):
        G = load_network(lat, lon, ntype)
        print(f"  {ntype}: {len(G.nodes)} nodes, {len(G.edges)} edges")
