"""Loads the prebuilt city-wide walk/bike network graphs (see citydata.py).

lat/lon are kept in the signature for call-site compatibility with the old
per-address download, but no longer select which graph is returned — every
address now shares the same city-wide graph, downloaded/loaded once per app
process instead of fetched live per request.
"""
from citydata import get_city_graph


def load_network(lat: float, lon: float, network_type: str):
    return get_city_graph(network_type)


if __name__ == "__main__":
    from geocode import geocode_address

    lat, lon = geocode_address("100 Queen St W")
    print(f"Coordinate: ({lat:.5f}, {lon:.5f})")

    for ntype in ("walk", "bike"):
        G = load_network(lat, lon, ntype)
        print(f"  {ntype}: {len(G.nodes)} nodes, {len(G.edges)} edges")
