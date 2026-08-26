"""Checks whether a Toronto address can plausibly support home EV charging,
by looking up the OpenStreetMap building at that point and classifying it by
building type.

This is a heuristic, not a definitive check: OSM's `building` tag describes
building form (house vs. apartment block), not whether a specific unit
actually has a private driveway or garage, and many Toronto buildings are
only generically tagged (`building=yes`). Treat the result as a starting
point for the "should I own an EV" question, not a verdict — the UI surfaces
the confidence level and note alongside the answer for exactly this reason.

Queries Overpass live per address (a single small-radius lookup, unlike
city-scorecard's original city-wide amenity queries) rather than needing a
prebuilt buildings dataset.
"""
from dataclasses import dataclass
from typing import Optional

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY_RADIUS_M = 40
# Overpass's frontend 406s requests carrying Python-requests' default
# User-Agent — a descriptive one is also just good practice per OSM's usage
# guidelines.
REQUEST_HEADERS = {"User-Agent": "toronto-ev-scorecard"}

# Building types with a private driveway/garage in the typical case.
HOUSE_TAGS = {"house", "detached", "semidetached_house", "bungalow", "cabin", "farm", "static_caravan"}
# Building types where a driveway/garage is common but not guaranteed.
CAVEAT_TAGS = {"terrace", "townhouse", "semi"}
# Building types that typically don't include private parking.
MULTI_UNIT_TAGS = {"apartments", "residential", "commercial", "retail", "office", "dormitory", "hotel", "industrial"}
# 4+ storeys is treated as multi-unit regardless of tag — a badly-tagged
# highrise shouldn't read as a single-family house.
MULTI_UNIT_LEVEL_THRESHOLD = 4


@dataclass
class HomeChargingResult:
    feasible: bool
    confidence: str        # "high", "medium", "low"
    dwelling_type: str      # raw OSM building tag, or "unknown"
    note: str


def _nearest_building(lat: float, lon: float) -> Optional[dict]:
    query = f"""
    [out:json][timeout:15];
    (
      way["building"](around:{QUERY_RADIUS_M},{lat},{lon});
      relation["building"](around:{QUERY_RADIUS_M},{lat},{lon});
    );
    out tags center;
    """
    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, headers=REQUEST_HEADERS, timeout=20)
            resp.raise_for_status()
            break
        except (requests.exceptions.HTTPError, requests.exceptions.Timeout):
            resp = None
    if resp is None:
        raise ValueError("Building lookup service (Overpass) is unavailable right now — try again shortly.")

    elements = resp.json().get("elements", [])
    if not elements:
        return None

    def _dist_sq(el: dict) -> float:
        center = el.get("center", {})
        return (center.get("lat", 0) - lat) ** 2 + (center.get("lon", 0) - lon) ** 2

    return min(elements, key=_dist_sq)


def check_home_charging(lat: float, lon: float) -> HomeChargingResult:
    building = _nearest_building(lat, lon)
    if building is None:
        return HomeChargingResult(
            feasible=False, confidence="low", dwelling_type="unknown",
            note=(
                "No building found nearby in OpenStreetMap — defaulting to public charging access. "
                "If you have a private driveway or garage, home charging is likely available regardless."
            ),
        )

    tags = building.get("tags", {})
    building_type = tags.get("building", "yes")
    levels_raw = tags.get("building:levels")
    try:
        levels = float(levels_raw) if levels_raw else None
    except ValueError:
        levels = None

    if levels is not None and levels >= MULTI_UNIT_LEVEL_THRESHOLD:
        return HomeChargingResult(
            feasible=False, confidence="high",
            dwelling_type=f"{building_type} ({int(levels)} storeys)",
            note="Building is tall enough to likely be multi-unit housing without private parking.",
        )

    if building_type in HOUSE_TAGS:
        return HomeChargingResult(
            feasible=True, confidence="high", dwelling_type=building_type,
            note="Detached/semi-detached homes typically have a private driveway or garage suitable for a Level 2 home charger.",
        )

    if building_type in CAVEAT_TAGS:
        return HomeChargingResult(
            feasible=True, confidence="medium", dwelling_type=building_type,
            note=(
                "Townhouses/row houses often have a private driveway or garage, but it varies by unit — "
                "confirm your own before assuming home charging is available."
            ),
        )

    if building_type in MULTI_UNIT_TAGS:
        return HomeChargingResult(
            feasible=False, confidence="high", dwelling_type=building_type,
            note="This building type typically doesn't include private parking — checking public charging access instead.",
        )

    return HomeChargingResult(
        feasible=False, confidence="low", dwelling_type=building_type,
        note=f"Building type '{building_type}' isn't specific enough to determine home charging feasibility — defaulting to public charging access.",
    )


if __name__ == "__main__":
    from geocode import geocode_address

    for address in ("100 Queen St W", "25 Rathburn Rd W, Etobicoke", "1 Yonge St"):
        lat, lon = geocode_address(address)
        result = check_home_charging(lat, lon)
        print(f"\n{address}")
        print(f"  feasible={result.feasible} ({result.confidence} confidence), type={result.dwelling_type!r}")
        print(f"  {result.note}")
