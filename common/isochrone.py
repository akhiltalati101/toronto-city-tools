"""15-minute travel isochrone over a street network graph — shared by
city-scorecard (walk + bike) and ev-scorecard (walk only), each passing its
own speed (see their isochrone.py).

Searches the graph by edge `length` with a distance cutoff and converts to
seconds afterwards, rather than writing a `travel_time` attribute onto every
edge first: the graphs are city-wide and cached process-wide (shared across
sessions), so the old per-request loop both cost a pass over every edge and
mutated shared state.
"""
from dataclasses import dataclass

import networkx as nx
import osmnx as ox
from shapely.geometry import MultiPoint, Polygon

TRAVEL_TIME_MIN = 15


@dataclass
class IsochroneResult:
    polygon: Polygon
    reachable: dict   # node_id -> travel time in seconds


def compute_isochrone(G, lat: float, lon: float, speed_kmh: float, minutes: float = TRAVEL_TIME_MIN) -> IsochroneResult:
    speed_mps = speed_kmh * 1000 / 3600
    center_node = ox.nearest_nodes(G, lon, lat)

    distances_m = nx.single_source_dijkstra_path_length(
        G, center_node, cutoff=minutes * 60 * speed_mps, weight="length"
    )
    reachable = {node: d / speed_mps for node, d in distances_m.items()}

    node_coords = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in reachable]
    if len(node_coords) < 3:
        raise ValueError("Too few reachable nodes to form an isochrone polygon.")

    polygon = MultiPoint(node_coords).convex_hull
    return IsochroneResult(polygon=polygon, reachable=reachable)
