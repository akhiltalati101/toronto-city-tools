"""Walk and bike isochrones for this app — see common/isochrone.py."""
from common.isochrone import IsochroneResult
from common.isochrone import compute_isochrone as _compute_isochrone

WALK_SPEED_KMH = 4.5
BIKE_SPEED_KMH = 15.0


def compute_isochrone(G, lat: float, lon: float, network_type: str) -> IsochroneResult:
    speed_kmh = BIKE_SPEED_KMH if network_type == "bike" else WALK_SPEED_KMH
    return _compute_isochrone(G, lat, lon, speed_kmh)


if __name__ == "__main__":
    from geocode import geocode_address
    from network import load_network

    lat, lon = geocode_address("100 Queen St W")
    print(f"Coordinate: ({lat:.5f}, {lon:.5f})")

    for ntype in ("walk", "bike"):
        G = load_network(lat, lon, ntype)
        result = compute_isochrone(G, lat, lon, ntype)
        print(f"  {ntype}: {len(result.reachable)} reachable nodes, area={result.polygon.area:.6f} deg²")
