"""Nearest-graph-node lookup with a cached spatial index.

Equivalent to osmnx.nearest_nodes on an unprojected (lat/lon) graph — the
same haversine BallTree, nearest by great-circle distance — except the tree
is built once per graph instead of on every call. On the city-wide walk graph
(~320k nodes) osmnx's per-call rebuild costs ~0.5-2 s, and one city score
makes eight such calls.
"""
from functools import lru_cache

import numpy as np
from sklearn.neighbors import BallTree


@lru_cache(maxsize=8)
def _index(G) -> tuple[np.ndarray, BallTree]:
    # Graphs hash by identity, and the city-wide ones live for the whole
    # process (see city/data.py), so this is built once per graph.
    node_ids = np.array(list(G.nodes))
    coords = np.radians([(G.nodes[n]["y"], G.nodes[n]["x"]) for n in node_ids])
    return node_ids, BallTree(coords, metric="haversine")


def nearest_nodes(G, X, Y):
    """Nearest node id to each (X=lon, Y=lat). Scalars in, scalar out; lists
    in, list out — same call shape as osmnx.nearest_nodes."""
    scalar = np.isscalar(X)
    node_ids, tree = _index(G)
    points = np.radians(np.column_stack([np.atleast_1d(Y), np.atleast_1d(X)]))
    if len(points) == 0:
        return []
    idx = tree.query(points, k=1, return_distance=False)[:, 0]
    nearest = node_ids[idx]
    return nearest[0].item() if scalar else nearest.tolist()


def warm(G) -> None:
    """Build G's index ahead of the first request."""
    _index(G)
