from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


def geocode_address(address: str, city_bias: str = "Toronto, Ontario") -> tuple[float, float]:
    """Return (lat, lon) for the given address string.

    Appends city_bias to the query if the address doesn't already contain it,
    so bare street addresses resolve within Toronto by default.

    Raises ValueError if the address cannot be found.
    """
    geolocator = Nominatim(user_agent="toronto-city-scorecard")

    query = address if city_bias.lower() in address.lower() else f"{address}, {city_bias}"

    try:
        location = geolocator.geocode(query, timeout=10)
    except GeocoderTimedOut:
        raise ValueError(f"Geocoding timed out for: {address!r}")
    except GeocoderServiceError as e:
        raise ValueError(f"Geocoding service error: {e}")

    if location is None:
        raise ValueError(f"Address not found: {address!r}")

    return (location.latitude, location.longitude)


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
