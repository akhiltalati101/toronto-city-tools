"""Address geocoding via Photon, restricted to Toronto — shared by all three
tools.

TORONTO_BBOX mirrors the bbox the apps' prebuilt data is built for (see
scripts/build_city_data.py and scripts/build_ev_data.py), and the area
tool's lookups are City of Toronto datasets.
An address outside it would silently snap to the nearest in-bounds graph
node or return empty results, so it's rejected here with a clear error.
"""
from __future__ import annotations

import re

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Photon

TORONTO_BBOX = (-79.64, 43.58, -79.11, 43.86)  # (minx, miny, maxx, maxy)

# Sent to Photon and Overpass, per OSM's usage guidelines (Overpass's
# frontend also 406s Python-requests' default User-Agent).
USER_AGENT = "toronto-city-tools"


def geocode_address(address: str, user_agent: str = USER_AGENT, city_bias: str = "Toronto, Ontario") -> tuple[float, float]:
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


def check_in_toronto(lat: float, lon: float) -> None:
    """Raise ValueError if (lat, lon) is outside TORONTO_BBOX."""
    minx, miny, maxx, maxy = TORONTO_BBOX
    if not (minx <= lon <= maxx and miny <= lat <= maxy):
        raise ValueError("Location is outside supported Toronto area")


def address_key(address: str) -> str:
    """Normalize an address for "is this the one we already scored?" checks,
    so a change in case, spacing, or commas alone doesn't count as new."""
    return re.sub(r"[\s,]+", " ", address).strip().casefold()


def resolve_location(address: str | None, lat: float | None = None, lon: float | None = None) -> tuple[str, float, float]:
    """Return (label, lat, lon) for either an address to geocode or a
    clicked map point. A point is checked against TORONTO_BBOX just like a
    geocoded address; its label is the address if one was given alongside
    it, else the coordinates themselves."""
    if lat is not None and lon is not None:
        check_in_toronto(lat, lon)
        return (address or f"{lat:.5f}, {lon:.5f}", lat, lon)
    if not address or not address.strip():
        raise ValueError("Enter an address first.")
    lat, lon = geocode_address(address)
    return (address, lat, lon)
