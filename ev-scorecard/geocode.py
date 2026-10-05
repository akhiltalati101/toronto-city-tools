"""Geocoding for this app — see common/geocode.py. Kept as a module so
call sites stay `from geocode import geocode_address`, with this app's own
User-Agent per OSM/Photon usage guidelines."""
from common.geocode import geocode_address as _geocode_address

USER_AGENT = "toronto-ev-scorecard"


def geocode_address(address: str, city_bias: str = "Toronto, Ontario") -> tuple[float, float]:
    return _geocode_address(address, USER_AGENT, city_bias)
