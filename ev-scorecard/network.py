"""Loads the prebuilt city-wide walk network graph (see data.py).

lat/lon are kept in the signature for call-site symmetry with city-scorecard's
network.py, though every address shares the same city-wide graph, downloaded/
loaded once per app process instead of fetched live per request.
"""
from data import get_walk_graph


def load_network(lat: float, lon: float):
    return get_walk_graph()


if __name__ == "__main__":
    from geocode import geocode_address

    lat, lon = geocode_address("100 Queen St W")
    G = load_network(lat, lon)
    print(f"walk: {len(G.nodes)} nodes, {len(G.edges)} edges")
