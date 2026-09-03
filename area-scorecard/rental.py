"""Rental building quality check — RentSafeTO's official apartment building
evaluation scores, looked up for the address if (and only if) it looks like
a registered rental apartment building.

Two steps:
  1. Classify the building via OpenStreetMap tags (adapted from
     ev-scorecard/home_charging.py's building lookup — copied rather than
     cross-imported, to keep the two apps independent) to decide whether a
     RentSafeTO lookup is even worth attempting.
  2. If it looks like an apartment building, match it against the RentSafeTO
     dataset (see data.py) by nearest coordinates — the dataset includes its
     own LATITUDE/LONGITUDE per building, which is far more reliable than
     fuzzy address-string matching, with a normalized-address fallback for
     the ~3% of rows missing coordinates.

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

import pandas as pd
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY_RADIUS_M = 40
REQUEST_HEADERS = {"User-Agent": "toronto-area-scorecard"}

HOUSE_TAGS = {"house", "detached", "semidetached_house", "bungalow", "cabin", "farm", "static_caravan"}
CAVEAT_TAGS = {"terrace", "townhouse", "semi"}
MULTI_UNIT_TAGS = {"apartments", "residential", "dormitory"}
MULTI_UNIT_LEVEL_THRESHOLD = 4

# A RentSafeTO row within this distance of the geocoded address is treated
# as the same building — small enough to not cross-match adjacent buildings
# on a dense downtown block, generous enough for GPS/geocoding jitter.
MATCH_RADIUS_M = 60

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
    is_apartment: bool
    dwelling_type: str
    note: str


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
    for _ in range(3):
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


def classify_building(lat: float, lon: float) -> BuildingClass:
    building = _nearest_building(lat, lon)
    if building is None:
        return BuildingClass(is_apartment=False, dwelling_type="unknown", note="No building found nearby in OpenStreetMap.")

    tags = building.get("tags", {})
    building_type = tags.get("building", "yes")
    levels_raw = tags.get("building:levels")
    try:
        levels = float(levels_raw) if levels_raw else None
    except ValueError:
        levels = None

    if levels is not None and levels >= MULTI_UNIT_LEVEL_THRESHOLD:
        return BuildingClass(
            is_apartment=True, dwelling_type=f"{building_type} ({int(levels)} storeys)",
            note="Building is tall enough to likely be an apartment/condo building.",
        )
    if building_type in MULTI_UNIT_TAGS:
        return BuildingClass(is_apartment=True, dwelling_type=building_type, note="Tagged as apartment-style housing in OpenStreetMap.")
    if building_type in HOUSE_TAGS:
        return BuildingClass(is_apartment=False, dwelling_type=building_type, note="Looks like a detached/semi-detached house — rental building checks don't apply.")
    if building_type in CAVEAT_TAGS:
        return BuildingClass(is_apartment=False, dwelling_type=building_type, note="Looks like a townhouse/row house — rental building checks don't apply.")

    return BuildingClass(is_apartment=False, dwelling_type=building_type, note=f"Building type '{building_type}' isn't clearly a multi-unit apartment building.")


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


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


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


def find_rentsafe_match(rentsafe_df: pd.DataFrame, address: str, lat: float, lon: float) -> Optional[RentSafeToScore]:
    """Match (lat, lon)/address against the RentSafeTO evaluations table,
    preferring nearest-coordinates and falling back to normalized address
    prefix matching. Returns the most recently evaluated row for the match.
    """
    candidates = rentsafe_df
    has_coords = candidates["LATITUDE"].notna() & candidates["LONGITUDE"].notna()
    nearby = candidates[has_coords].copy()
    if not nearby.empty:
        nearby["_dist_m"] = nearby.apply(
            lambda r: _haversine_m(lat, lon, float(r["LATITUDE"]), float(r["LONGITUDE"])), axis=1
        )
        nearby = nearby[nearby["_dist_m"] <= MATCH_RADIUS_M]

    if nearby.empty:
        normalized = _normalize_address(address)
        street_prefix = " ".join(normalized.split(" ")[:3])  # e.g. "123 MAIN ST"
        nearby = candidates[candidates["SITE ADDRESS"].apply(_normalize_address).str.startswith(street_prefix)]

    if nearby.empty:
        return None

    matched_site = nearby.iloc[0]["SITE ADDRESS"]
    building_rows = candidates[candidates["SITE ADDRESS"] == matched_site]
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
    building = classify_building(lat, lon)
    if not building.is_apartment:
        return RentalResult(building=building, rentsafe=None, facebook_search_url=None)

    match = find_rentsafe_match(rentsafe_df, address, lat, lon)
    fb_url = None
    if match is None:
        fb_url = FACEBOOK_GROUP_SEARCH_URL + requests.utils.quote(address)
    return RentalResult(building=building, rentsafe=match, facebook_search_url=fb_url)


if __name__ == "__main__":
    from data import get_rentsafe_data
    from geocode import geocode_address

    df = get_rentsafe_data()
    print(f"Loaded {len(df)} RentSafeTO evaluation rows")

    for address in ("2515 Lake Shore Blvd W", "100 Queen St W", "35 Playter Blvd"):
        lat, lon = geocode_address(address)
        result = check_rental(lat, lon, address, df)
        print(f"\n=== {address} ===")
        print(f"  building: {result.building.dwelling_type} (apartment={result.building.is_apartment}) — {result.building.note}")
        if result.rentsafe:
            r = result.rentsafe
            print(f"  RentSafeTO match: {r.address} — score {r.overall_score}, evaluated {r.evaluated_on}, "
                  f"{r.storeys} storeys / {r.units} units")
            print(f"  lowest categories: {r.lowest_categories}")
        elif result.facebook_search_url:
            print(f"  no RentSafeTO match — likely a condo corp, not a registered rental. {result.facebook_search_url}")
