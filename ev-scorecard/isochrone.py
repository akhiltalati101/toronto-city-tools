"""15-minute walk isochrone around an address — the catchment used to check
for nearby public charging (see charger_access.py). Walk-only; unlike
city-scorecard, EV access doesn't need a bike isochrone. The search itself
is common/isochrone.py.
"""
from common.isochrone import TRAVEL_TIME_MIN, IsochroneResult
from common.isochrone import compute_isochrone as _compute_isochrone

WALK_SPEED_KMH = 4.5


def compute_isochrone(G, lat: float, lon: float) -> IsochroneResult:
    # TRAVEL_TIME_MIN is also imported from here by charger_access.py.
    return _compute_isochrone(G, lat, lon, WALK_SPEED_KMH, TRAVEL_TIME_MIN)


if __name__ == "__main__":
    from geocode import geocode_address
    from network import load_network

    lat, lon = geocode_address("100 Queen St W")
    G = load_network(lat, lon)
    result = compute_isochrone(G, lat, lon)
    print(f"walk: {len(result.reachable)} reachable nodes, area={result.polygon.area:.6f} deg²")
