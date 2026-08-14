from dataclasses import dataclass

import networkx as nx
import osmnx as ox
from shapely.geometry import MultiPoint, Polygon

WALK_SPEED_KMH = 4.5
BIKE_SPEED_KMH = 15.0
TRAVEL_TIME_MIN = 15


@dataclass
class IsochroneResult:
    polygon: Polygon
    reachable: dict   # node_id -> travel time in seconds


def _speed_for(network_type: str) -> float:
    return BIKE_SPEED_KMH if network_type == "bike" else WALK_SPEED_KMH


def compute_isochrone(G, lat: float, lon: float, network_type: str) -> IsochroneResult:
    speed_kmh = _speed_for(network_type)
    cutoff_sec = TRAVEL_TIME_MIN * 60

    for _, _, data in G.edges(data=True):
        data["travel_time"] = data["length"] / (speed_kmh * 1000 / 3600)

    center_node = ox.nearest_nodes(G, lon, lat)

    reachable = nx.single_source_dijkstra_path_length(
        G, center_node, cutoff=cutoff_sec, weight="travel_time"
    )

    node_coords = [
        (G.nodes[n]["x"], G.nodes[n]["y"]) for n in reachable
    ]

    if len(node_coords) < 3:
        raise ValueError("Too few reachable nodes to form an isochrone polygon.")

    polygon = MultiPoint(node_coords).convex_hull
    return IsochroneResult(polygon=polygon, reachable=dict(reachable))


if __name__ == "__main__":
    from geocode import geocode_address
    from network import load_network

    lat, lon = geocode_address("100 Queen St W")
    print(f"Coordinate: ({lat:.5f}, {lon:.5f})")

    for ntype in ("walk", "bike"):
        G = load_network(lat, lon, ntype)
        result = compute_isochrone(G, lat, lon, ntype)
        print(f"  {ntype}: {len(result.reachable)} reachable nodes, area={result.polygon.area:.6f} deg²")
