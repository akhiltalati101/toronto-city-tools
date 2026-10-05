"""Address geocoding via Photon, restricted to Toronto — shared by all three
apps, each passing its own User-Agent (see their geocode.py).

TORONTO_BBOX mirrors the bbox the apps' prebuilt data is built for (see
city-scorecard/scripts/build_city_data.py and ev-scorecard/scripts/
build_ev_data.py), and area-scorecard's lookups are City of Toronto datasets.
An address outside it would silently snap to the nearest in-bounds graph
node or return empty results, so it's rejected here with a clear error.
"""
import re

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Photon

TORONTO_BBOX = (-79.64, 43.58, -79.11, 43.86)  # (minx, miny, maxx, maxy)


def geocode_address(address: str, user_agent: str, city_bias: str = "Toronto, Ontario") -> tuple[float, float]:
    """Return (lat, lon) for the given address string.

    Appends city_bias to the query if the address doesn't already contain it,
    so bare street addresses resolve within Toronto by default.

    Raises ValueError if the address cannot be found or falls outside the
    supported Toronto area.
    """
    geolocator = Photon(user_agent=user_agent)

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


def address_key(address: str) -> str:
    """Normalize an address for "is this the one we already scored?" checks,
    so a change in case, spacing, or commas alone doesn't count as new."""
    return re.sub(r"[\s,]+", " ", address).strip().casefold()


if __name__ == "__main__":
    for addr in ("100 Queen St W", "1 Yonge St", "this is not a real place 99999"):
        try:
            lat, lon = geocode_address(addr, "toronto-city-tools-selftest")
            print(f"OK  {addr!r:40s} -> ({lat:.5f}, {lon:.5f})")
        except ValueError as e:
            print(f"ERR {addr!r:40s} -> {e}")
