"""A small synthetic street graph around the overpass_fixtures origin, shaped
like the osmnx MultiDiGraphs the app loads from its city-wide pickles."""
import networkx as nx

from overpass_fixtures import at


def grid(n=21, spacing_m=80):
    """n x n street grid centred on the fixture origin, with one-way and
    parallel edges mixed in, shaped like an osmnx MultiDiGraph."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    node = lambda i, j: i * n + j  # noqa: E731  (osmnx needs scalar node ids)
    for i in range(n):
        for j in range(n):
            lat, lon = at((i - n // 2) * spacing_m, (j - n // 2) * spacing_m)
            G.add_node(node(i, j), x=lon, y=lat)
    for i in range(n):
        for j in range(n):
            for di, dj in ((1, 0), (0, 1)):
                if i + di < n and j + dj < n:
                    length = spacing_m * (1 + 0.1 * ((i * 7 + j * 3) % 5))
                    G.add_edge(node(i, j), node(i + di, j + dj), length=length)
                    if (i + j) % 4:  # every 4th edge is one-way
                        G.add_edge(node(i + di, j + dj), node(i, j), length=length)
    G.add_edge(node(10, 10), node(10, 11), length=10.0)  # shorter parallel edge
    return G
