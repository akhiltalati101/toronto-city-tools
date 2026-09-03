from geopy.geocoders import Photon
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Mirrors ev-scorecard/geocode.py's TORONTO_BBOX — the AIC, crime, and
# RentSafeTO lookups are all Toronto-specific (crime/RentSafeTO are literally
# City of Toronto datasets; the AIC layer does cover some non-Toronto
# corridors but scoring elsewhere assumes Toronto), so addresses outside it
# would silently return empty results instead of erroring.
TORONTO_BBOX = (-79.64, 43.58, -79.11, 43.86)  # (minx, miny, maxx, maxy)


def geocode_address(address: str, city_bias: str = "Toronto, Ontario") -> tuple[float, float]:
    """Return (lat, lon) for the given address string.

    Appends city_bias to the query if the address doesn't already contain it,
    so bare street addresses resolve within Toronto by default.

    Raises ValueError if the address cannot be found or falls outside the
    supported Toronto area.
    """
    geolocator = Photon(user_agent="toronto-area-scorecard")

    query = address if city_bias.lower() in address.lower() else f"{address}, {city_bias}"

    try:
        location = geolocator.geocode(query, timeout=10)
    except GeocoderTimedOut:
        raise ValueError(f"Geocoding timed out for: {address!r}")
    except GeocoderServiceError as e:
        raise ValueError(f"Geocoding service error: {e}")

    if location is None:
        raise ValueError(f"Address not found: {address!r}")

    lat, lon = location.latitude, location.longitude
    minx, miny, maxx, maxy = TORONTO_BBOX
    if not (minx <= lon <= maxx and miny <= lat <= maxy):
        raise ValueError("Address is outside supported Toronto area")

    return (lat, lon)


if __name__ == "__main__":
    tests = [
        "100 Queen St W",
        "1 Yonge St",
        "this is not a real place 99999",
    ]
    for addr in tests:
        try:
            lat, lon = geocode_address(addr)
            print(f"OK  {addr!r:40s} -> ({lat:.5f}, {lon:.5f})")
        except ValueError as e:
            print(f"ERR {addr!r:40s} -> {e}")
