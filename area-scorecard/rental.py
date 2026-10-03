"""Rental building quality check — RentSafeTO's official apartment building
evaluation scores, looked up for the address if (and only if) it looks like
a registered rental apartment building.

RentSafeTO first, OSM classification second:
  1. Look up the OpenStreetMap building footprint at the address (via
     common/buildings.py, shared with ev-scorecard) and match the RentSafeTO
     dataset against it — a RentSafeTO row whose own LATITUDE/LONGITUDE falls
     inside the footprint, else a normalized-address match, else (only if
     the address isn't inside any footprint) the nearest row within
     MATCH_RADIUS_M.
     A match settles the question outright: it's a registered rental
     apartment building, however OSM happens to tag it. Most Toronto towers
     are tagged plain `building=yes`, so gating the lookup on OSM tags — as
     this used to — skipped exactly the buildings RentSafeTO covers.
  2. Only if nothing matches, classify the building from its OSM tags into
     apartment / not an apartment / unknown, so the UI can say "probably a
     condo" only when OSM actually indicates multi-unit housing, and "can't
     tell" when the tag is generic.

Important limitation surfaced to the user: RentSafeTO only covers registered
*rental* apartment buildings (3+ storeys or 10+ units) — it does not cover
owner-occupied condo corporations, a large share of what "condo" means in
Toronto. An unmatched multi-unit building very plausibly means "this is a
condo corp, not a rental," not "no data available" — the UI should say so
plainly and fall back to a Facebook group search link instead of a blank.
"""
import math
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point, Polygon

from common import buildings

USER_AGENT = "toronto-area-scorecard"

# Without a footprint to check against, a RentSafeTO row within this distance
# of the geocoded address is treated as the same building — small enough to
# not cross-match adjacent buildings on a dense downtown block, generous
# enough for GPS/geocoding jitter.
MATCH_RADIUS_M = 60
# RentSafeTO coordinates are often an address point on the building's
# frontage rather than inside the footprint, so the footprint is grown by
# roughly this much (in degrees, ~15-20 m) before the containment check.
FOOTPRINT_BUFFER_DEG = 0.0002
# An address-string match must also be within this distance, so "100 Queen
# St" can't match 100 Queen St E when the geocoder resolved Queen St W.
ADDRESS_MATCH_MAX_M = 500

# Building statuses for the rental check.
APARTMENT = "apartment"
NOT_APARTMENT = "not_apartment"
UNKNOWN = "unknown"

# Category columns worth surfacing as "what's actually wrong" — the closest
# legitimate proxy this data offers for tenant complaints like "the elevator
# has been out for months." Scored 1 (worst) to 3 (best) per RentSafeTO's
# own methodology; N/A means not applicable to this building.
HIGHLIGHT_CATEGORIES = [
    "ELEVATOR MAINTENANCE", "ELEVATOR COSMETICS", "GARBAGE/COMPACTOR ROOM",
    "COMMON AREA PESTS", "PARKING AREAS", "INTERCOM", "BUILDING CLEANLINESS",
    "SECURITY", "GRAFFITI", "COMMON AREA VENTILATION",
]

FACEBOOK_GROUP_SEARCH_URL = "https://www.facebook.com/search/groups/?q="


@dataclass
class BuildingClass:
    status: str          # APARTMENT, NOT_APARTMENT, or UNKNOWN
    dwelling_type: str
    note: str

    @property
    def is_apartment(self) -> bool:
        return self.status == APARTMENT


@dataclass
class RentSafeToScore:
    address: str
    overall_score: Optional[int]
    evaluated_on: Optional[str]
    storeys: Optional[int]
    units: Optional[int]
    property_type: Optional[str]
    lowest_categories: list[tuple[str, int]]  # [(category, score_1_to_3), ...] worst first


@dataclass
class RentalResult:
    building: BuildingClass
    rentsafe: Optional[RentSafeToScore]
    facebook_search_url: Optional[str]


def classify_building(building: Optional[buildings.Building], lookup_failed: bool = False) -> BuildingClass:
    """Classify an OSM building for the rental check. Only called when there's
    no RentSafeTO match, so notes are written for that case."""
    if lookup_failed:
        return BuildingClass(UNKNOWN, "unknown", "The building lookup service (OpenStreetMap) didn't respond, so the building type couldn't be checked.")
    if building is None:
        return BuildingClass(UNKNOWN, "unknown", "No building found nearby in OpenStreetMap.")

    building_class = buildings.classify(building)
    kind, dwelling_type = building_class.kind, building_class.dwelling_type
    if kind == buildings.MULTI_UNIT:
        return BuildingClass(APARTMENT, dwelling_type, "Mapped as apartment-style housing in OpenStreetMap.")
    if kind == buildings.HOUSE:
        return BuildingClass(NOT_APARTMENT, dwelling_type, "Looks like a detached/semi-detached house — rental building checks don't apply.")
    if kind == buildings.TOWNHOUSE:
        return BuildingClass(NOT_APARTMENT, dwelling_type, "Looks like a townhouse/row house — rental building checks don't apply.")
    if kind == buildings.NON_RESIDENTIAL:
        return BuildingClass(NOT_APARTMENT, dwelling_type, f"Mapped as a {dwelling_type} building, and it isn't registered with RentSafeTO — rental building checks don't apply.")
    return BuildingClass(UNKNOWN, dwelling_type, f"OpenStreetMap only tags this as building='{dwelling_type}', which doesn't say whether it's an apartment building.")


_SUFFIX_MAP = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "ROAD": "RD", "DRIVE": "DR",
    "CRESCENT": "CRES", "COURT": "CRT", "PLACE": "PL", "LANE": "LN", "CIRCLE": "CIRC",
    "SQUARE": "SQ", "TERRACE": "TER", "GARDENS": "GDNS", "PARKWAY": "PKWY",
    "WEST": "W", "EAST": "E", "NORTH": "N", "SOUTH": "S",
}


def _normalize_address(address: str) -> str:
    text = re.sub(r"[.,]", "", address.upper())
    text = re.sub(r"\s+", " ", text).strip()
    words = [_SUFFIX_MAP.get(w, w) for w in text.split(" ")]
    return " ".join(words)


def _haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres; vectorized over numpy arrays."""
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(np.asarray(lat2) - lat1)
    dlambda = np.radians(np.asarray(lon2) - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _lowest_categories(row: pd.Series, n: int = 3) -> list[tuple[str, int]]:
    scored = []
    for col in HIGHLIGHT_CATEGORIES:
        val = row.get(col)
        try:
            score = int(val)
        except (TypeError, ValueError):
            continue
        if score in (1, 2, 3):
            scored.append((col.title(), score))
    scored.sort(key=lambda t: t[1])
    return scored[:n]


def _match_site(
    rentsafe_df: pd.DataFrame, address: str, lat: float, lon: float,
    footprint: Optional[Polygon],
) -> Optional[str]:
    """Return the SITE ADDRESS of the RentSafeTO building at this location, or None."""
    dist_m = pd.Series(
        _haversine_m(lat, lon, rentsafe_df["LATITUDE"].to_numpy(), rentsafe_df["LONGITUDE"].to_numpy()),
        index=rentsafe_df.index,
    )  # NaN where the row has no coordinates

    # 1. A RentSafeTO point inside the address's own footprint.
    if footprint is not None:
        grown = footprint.buffer(FOOTPRINT_BUFFER_DEG)
        near = rentsafe_df[dist_m <= ADDRESS_MATCH_MAX_M]
        inside = [
            idx for idx, row in near.iterrows()
            if grown.contains(Point(row["LONGITUDE"], row["LATITUDE"]))
        ]
        if inside:
            return rentsafe_df.loc[dist_m.loc[inside].idxmin(), "SITE ADDRESS"]

    # 2. Same street number and name. Rows without coordinates (~3%) can only
    # be found this way, so they're accepted without the distance check.
    street_prefix = " ".join(_normalize_address(address).split(" ")[:3])  # e.g. "123 MAIN ST"
    by_address = rentsafe_df["SITE ADDRESS"].apply(_normalize_address).str.startswith(street_prefix)
    by_address &= dist_m.isna() | (dist_m <= ADDRESS_MATCH_MAX_M)
    if by_address.any():
        return rentsafe_df.loc[dist_m[by_address].fillna(math.inf).idxmin(), "SITE ADDRESS"]

    # 3. Nearest row within MATCH_RADIUS_M — only when the address isn't
    # inside any mapped footprint. When it is, a RentSafeTO point outside
    # that footprint belongs to a different building: plenty of Toronto
    # houses are tagged plain `building=yes`, and matching them by radius
    # would report the apartment tower next door.
    if footprint is None:
        within = dist_m[dist_m <= MATCH_RADIUS_M]
        if not within.empty:
            return rentsafe_df.loc[within.idxmin(), "SITE ADDRESS"]
    return None


def find_rentsafe_match(
    rentsafe_df: pd.DataFrame, address: str, lat: float, lon: float,
    building: Optional[buildings.Building] = None,
) -> Optional[RentSafeToScore]:
    """Match the address against the RentSafeTO evaluations table (see module
    docstring for the order). Returns the most recently evaluated row for the
    matched building.
    """
    footprint = building.footprint if building is not None and building.contains_point else None
    matched_site = _match_site(rentsafe_df, address, lat, lon, footprint)
    if matched_site is None:
        return None

    building_rows = rentsafe_df[rentsafe_df["SITE ADDRESS"] == matched_site]
    latest = building_rows.sort_values("EVALUATION COMPLETED ON", ascending=False).iloc[0]

    def _int_or_none(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    return RentSafeToScore(
        address=matched_site,
        overall_score=_int_or_none(latest.get("CURRENT BUILDING EVAL SCORE")),
        evaluated_on=latest.get("EVALUATION COMPLETED ON") or None,
        storeys=_int_or_none(latest.get("CONFIRMED STOREYS")),
        units=_int_or_none(latest.get("CONFIRMED UNITS")),
        property_type=latest.get("PROPERTY TYPE") or None,
        lowest_categories=_lowest_categories(latest),
    )


def check_rental(lat: float, lon: float, address: str, rentsafe_df: pd.DataFrame) -> RentalResult:
    # An Overpass outage degrades this card rather than failing the whole
    # scorecard: RentSafeTO matching still works by address and radius.
    lookup_failed = False
    try:
        building = buildings.fetch_building(lat, lon, USER_AGENT)
    except ValueError:
        building, lookup_failed = None, True

    match = find_rentsafe_match(rentsafe_df, address, lat, lon, building)
    if match is not None:
        dwelling_type = match.property_type or "apartment building"
        return RentalResult(
            building=BuildingClass(APARTMENT, dwelling_type, "Registered with RentSafeTO as a rental apartment building."),
            rentsafe=match, facebook_search_url=None,
        )

    building_class = classify_building(building, lookup_failed)
    fb_url = None
    if building_class.status != NOT_APARTMENT:
        fb_url = FACEBOOK_GROUP_SEARCH_URL + requests.utils.quote(address)
    return RentalResult(building=building_class, rentsafe=None, facebook_search_url=fb_url)


if __name__ == "__main__":
    from data import get_rentsafe_data
    from geocode import geocode_address

    df = get_rentsafe_data()
    print(f"Loaded {len(df)} RentSafeTO evaluation rows")

    for address in ("2515 Lake Shore Blvd W", "100 Queen St W", "35 Playter Blvd"):
        lat, lon = geocode_address(address)
        result = check_rental(lat, lon, address, df)
        print(f"\n=== {address} ===")
        print(f"  building: {result.building.dwelling_type} ({result.building.status}) — {result.building.note}")
        if result.rentsafe:
            r = result.rentsafe
            print(f"  RentSafeTO match: {r.address} — score {r.overall_score}, evaluated {r.evaluated_on}, "
                  f"{r.storeys} storeys / {r.units} units")
            print(f"  lowest categories: {r.lowest_categories}")
        elif result.facebook_search_url:
            print(f"  no RentSafeTO match — likely a condo corp, not a registered rental. {result.facebook_search_url}")
