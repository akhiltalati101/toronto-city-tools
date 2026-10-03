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
prebuilt buildings dataset. The lookup and tag classification live in
common/buildings.py, shared with area-scorecard.
"""
from dataclasses import dataclass

from common.buildings import (
    HOUSE, MULTI_UNIT, NON_RESIDENTIAL, TOWNHOUSE, classify, fetch_building,
)

USER_AGENT = "toronto-ev-scorecard"

_LOWER_CONFIDENCE = {"high": "medium", "medium": "low", "low": "low"}


@dataclass
class HomeChargingResult:
    feasible: bool
    confidence: str        # "high", "medium", "low"
    dwelling_type: str      # raw OSM building tag, or "unknown"
    note: str


def _classify_for_charging(kind: str, dwelling_type: str) -> HomeChargingResult:
    if kind == HOUSE:
        return HomeChargingResult(
            feasible=True, confidence="high", dwelling_type=dwelling_type,
            note="Detached/semi-detached homes typically have a private driveway or garage suitable for a Level 2 home charger.",
        )
    if kind == TOWNHOUSE:
        return HomeChargingResult(
            feasible=True, confidence="medium", dwelling_type=dwelling_type,
            note=(
                "Townhouses/row houses often have a private driveway or garage, but it varies by unit — "
                "confirm your own before assuming home charging is available."
            ),
        )
    if kind == MULTI_UNIT:
        return HomeChargingResult(
            feasible=False, confidence="high", dwelling_type=dwelling_type,
            note="This looks like multi-unit housing, which typically doesn't include private parking — checking public charging access instead.",
        )
    if kind == NON_RESIDENTIAL:
        return HomeChargingResult(
            feasible=False, confidence="high", dwelling_type=dwelling_type,
            note="This building type typically doesn't include private parking — checking public charging access instead.",
        )
    return HomeChargingResult(
        feasible=False, confidence="low", dwelling_type=dwelling_type,
        note=(
            f"Building type '{dwelling_type}' isn't specific enough to determine home charging feasibility — "
            "defaulting to public charging access. If you have a private driveway or garage, home charging is "
            "likely available regardless."
        ),
    )


def check_home_charging(lat: float, lon: float) -> HomeChargingResult:
    building = fetch_building(lat, lon, USER_AGENT)
    if building is None:
        return HomeChargingResult(
            feasible=False, confidence="low", dwelling_type="unknown",
            note=(
                "No building found nearby in OpenStreetMap — defaulting to public charging access. "
                "If you have a private driveway or garage, home charging is likely available regardless."
            ),
        )

    building_class = classify(building)
    result = _classify_for_charging(building_class.kind, building_class.dwelling_type)
    if not building.contains_point:
        # The address didn't land inside any footprint, so this is the
        # nearest building — usually right, but on a mixed block it can be
        # the neighbour.
        result.confidence = _LOWER_CONFIDENCE[result.confidence]
        result.note += " (Based on the nearest mapped building — the address didn't fall inside a building outline.)"
    return result


if __name__ == "__main__":
    from geocode import geocode_address

    for address in ("100 Queen St W", "25 Rathburn Rd W, Etobicoke", "1 Yonge St"):
        lat, lon = geocode_address(address)
        result = check_home_charging(lat, lon)
        print(f"\n{address}")
        print(f"  feasible={result.feasible} ({result.confidence} confidence), type={result.dwelling_type!r}")
        print(f"  {result.note}")
