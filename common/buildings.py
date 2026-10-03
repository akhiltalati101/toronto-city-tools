"""OpenStreetMap building lookup and building-type classification, shared by
ev-scorecard (home charging feasibility) and area-scorecard (whether a
RentSafeTO lookup applies).

Lookup: fetch every building footprint within QUERY_RADIUS_M of the geocoded
point, with full geometry, and prefer the footprint that actually *contains*
the point. Only if no footprint contains it (geocoders often drop the point
on the street or the lot's front yard) fall back to the footprint whose
edge is nearest. Comparing centroids instead, as this used to, picks the
wrong building whenever a small neighbour's centroid sits closer to the
point than a large building's — e.g. a corner house beside a long
apartment slab.

Classification is deliberately three-valued at heart (multi-unit / house /
unknown, plus townhouse and non-residential refinements): most Toronto
buildings are generically tagged `building=yes`, and `building=residential`
is used for everything from bungalows to towers, so neither is evidence
either way. Callers must treat UNKNOWN as "can't tell", not as a negative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY_RADIUS_M = 40

# Building kinds returned by classify().
HOUSE = "house"                     # detached/semi — private driveway typical
TOWNHOUSE = "townhouse"             # row/townhouse — driveway varies by unit
MULTI_UNIT = "multi_unit"           # apartment/condo building
NON_RESIDENTIAL = "non_residential"
UNKNOWN = "unknown"                 # tag not specific enough (yes, residential, ...)

HOUSE_TAGS = {"house", "detached", "semidetached_house", "bungalow", "cabin", "farm", "static_caravan"}
TOWNHOUSE_TAGS = {"terrace", "townhouse", "semi"}
MULTI_UNIT_TAGS = {"apartments", "dormitory"}
NON_RESIDENTIAL_TAGS = {"commercial", "retail", "office", "hotel", "industrial"}
# 4+ storeys is treated as multi-unit unless the tag says non-residential —
# a badly-tagged highrise shouldn't read as a single-family house.
MULTI_UNIT_LEVEL_THRESHOLD = 4


@dataclass
class Building:
    tags: dict
    footprint: Optional[Polygon]   # lon/lat coordinates; None if geometry was unusable
    contains_point: bool           # footprint contains the geocoded point (vs. merely nearest)

    @property
    def building_type(self) -> str:
        return self.tags.get("building", "yes")

    @property
    def levels(self) -> Optional[float]:
        try:
            return float(self.tags["building:levels"])
        except (KeyError, ValueError):
            return None


@dataclass
class BuildingClass:
    kind: str            # one of HOUSE, TOWNHOUSE, MULTI_UNIT, NON_RESIDENTIAL, UNKNOWN
    dwelling_type: str   # human-readable raw tag, e.g. "apartments" or "yes (12 storeys)"


def _footprint(element: dict) -> Optional[Polygon]:
    """Build a footprint from an Overpass `out geom` way or multipolygon relation."""
    if element.get("type") == "way":
        coords = [(p["lon"], p["lat"]) for p in element.get("geometry", []) if p]
        if len(coords) < 4:
            return None
        poly = Polygon(coords)
        return poly if poly.is_valid else poly.buffer(0)

    # Relation: outer rings may be split across several member ways, so stitch
    # them with polygonize rather than assuming each member is closed.
    lines = [
        LineString([(p["lon"], p["lat"]) for p in m["geometry"] if p])
        for m in element.get("members", [])
        if m.get("type") == "way" and m.get("role", "") in ("outer", "") and len(m.get("geometry", [])) >= 2
    ]
    polys = list(polygonize(lines))
    if not polys:
        return None
    merged = unary_union(polys)
    return merged if merged.geom_type == "Polygon" else max(merged.geoms, key=lambda g: g.area)


def pick_building(elements: list[dict], lat: float, lon: float) -> Optional[Building]:
    """Choose the building for (lat, lon) from Overpass `out tags geom` elements:
    the smallest footprint containing the point, else the nearest footprint edge.
    Split out from fetch_building so it can be tested against saved responses."""
    point = Point(lon, lat)
    candidates = [(el.get("tags", {}), _footprint(el)) for el in elements]
    candidates = [(tags, fp) for tags, fp in candidates if fp is not None and not fp.is_empty]
    if not candidates:
        return None

    containing = [(tags, fp) for tags, fp in candidates if fp.contains(point)]
    if containing:
        # Smallest wins: a point inside a building nested within a larger
        # outline (courtyard blocks, podium + tower) belongs to the inner one.
        tags, fp = min(containing, key=lambda c: c[1].area)
        return Building(tags=tags, footprint=fp, contains_point=True)

    tags, fp = min(candidates, key=lambda c: c[1].distance(point))
    return Building(tags=tags, footprint=fp, contains_point=False)


def fetch_building(lat: float, lon: float, user_agent: str) -> Optional[Building]:
    """Look up the OSM building at (lat, lon). Returns None if there's no
    building within QUERY_RADIUS_M; raises ValueError if Overpass is down.

    `user_agent` is required: Overpass's frontend 406s requests carrying
    Python-requests' default User-Agent, and a descriptive one is good
    practice per OSM's usage guidelines anyway.
    """
    query = f"""
    [out:json][timeout:15];
    (
      way["building"](around:{QUERY_RADIUS_M},{lat},{lon});
      relation["building"](around:{QUERY_RADIUS_M},{lat},{lon});
    );
    out tags geom;
    """
    resp = None
    for _ in range(3):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": user_agent}, timeout=20)
            resp.raise_for_status()
            break
        except (requests.exceptions.HTTPError, requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            resp = None
    if resp is None:
        raise ValueError("Building lookup service (Overpass) is unavailable right now — try again shortly.")

    return pick_building(resp.json().get("elements", []), lat, lon)


def classify(building: Building) -> BuildingClass:
    building_type = building.building_type
    levels = building.levels

    if building_type in NON_RESIDENTIAL_TAGS:
        return BuildingClass(NON_RESIDENTIAL, building_type)
    if levels is not None and levels >= MULTI_UNIT_LEVEL_THRESHOLD:
        return BuildingClass(MULTI_UNIT, f"{building_type} ({int(levels)} storeys)")
    if building_type in MULTI_UNIT_TAGS:
        return BuildingClass(MULTI_UNIT, building_type)
    if building_type in HOUSE_TAGS:
        return BuildingClass(HOUSE, building_type)
    if building_type in TOWNHOUSE_TAGS:
        return BuildingClass(TOWNHOUSE, building_type)
    return BuildingClass(UNKNOWN, building_type)
