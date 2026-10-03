"""Builders for Overpass `out tags geom` responses, laid out in metres around
a fixed Toronto origin so test geometry is readable."""
import math

ORIGIN_LAT, ORIGIN_LON = 43.6500, -79.3800
M_PER_DEG_LAT = 111_320
M_PER_DEG_LON = 111_320 * math.cos(math.radians(ORIGIN_LAT))


def at(x_m: float, y_m: float) -> tuple[float, float]:
    """(lat, lon) for a point x_m east and y_m north of the origin."""
    return ORIGIN_LAT + y_m / M_PER_DEG_LAT, ORIGIN_LON + x_m / M_PER_DEG_LON


def _ring(x0, y0, x1, y1) -> list[dict]:
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return [dict(zip(("lat", "lon"), at(x, y))) for x, y in corners]


def way(x0, y0, x1, y1, **tags) -> dict:
    """Rectangular building way spanning (x0, y0)-(x1, y1) metres."""
    return {"type": "way", "id": hash((x0, y0, x1, y1)) & 0xFFFF, "tags": tags, "geometry": _ring(x0, y0, x1, y1)}


def split_relation(x0, y0, x1, y1, **tags) -> dict:
    """Multipolygon relation whose rectangular outer ring is split across two
    member ways, as long building outlines often are in OSM."""
    ring = _ring(x0, y0, x1, y1)
    return {
        "type": "relation", "id": 1, "tags": tags,
        "members": [
            {"type": "way", "ref": 10, "role": "outer", "geometry": ring[:3]},
            {"type": "way", "ref": 11, "role": "outer", "geometry": ring[2:]},
        ],
    }
