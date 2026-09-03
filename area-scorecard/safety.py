"""Live 6-month crime comparison for the area around an address — Toronto
Police's "Community Safety Indicators" (formerly Major Crime Indicators)
data, queried directly per request rather than pre-fetched: a 6-month,
fixed-radius window is a small result set, and querying live keeps the
comparison current without a rebuild pipeline.

Two live queries per request:
  1. Local incidents — a point+radius spatial query, 6-month date filter.
  2. Citywide baseline — an aggregate (outStatistics) query over the same
     6-month window, grouped by offence, with no geometry filter. Cheap
     (one row per offence subtype back, not one row per incident) and cached
     by the caller (see app.py) since the citywide rate moves slowly.

Incident locations in this dataset are deliberately offset to the nearest
road intersection by the Toronto Police Service to protect privacy — see
https://data.tps.ca — so this uses a straight-line radius buffer rather than
the walk-network isochrones used elsewhere in this repo family; routing
precision would be wasted on already-fuzzed points.
"""
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

CSI_FEATURESERVER_URL = (
    "https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/"
    "Major_Crime_Indicators_Open_Data/FeatureServer/0/query"
)

SEARCH_RADIUS_M = 500
WINDOW_DAYS = 182  # ~6 months

# City of Toronto's official land area, used only to convert the citywide
# aggregate count into an expected count for a circle of SEARCH_RADIUS_M —
# an approximation, not a precise density model (crime is not uniformly
# distributed across the city), but reasonable for a directional "safer/
# about average/less safe than the city as a whole" comparison.
TORONTO_LAND_AREA_KM2 = 630.2

# Per-offence-subtype severity weights (falls back to the category-level
# default below when a subtype isn't listed). Calibrated by hand against the
# subtype list returned by the live API (see the module's __main__ block, or
# query CSI_CATEGORY/OFFENCE with a groupBy count to see the full list) —
# intentionally rough (this is "how worried should a resident be," not a
# criminological model): weapon-involved and home-invasion-style subtypes
# weight highest, minor theft-of-property subtypes lowest.
OFFENCE_WEIGHTS: dict[str, float] = {
    "Assault": 1.0,
    "Assault With Weapon": 2.0,
    "Assault Bodily Harm": 1.5,
    "Aggravated Assault": 3.0,
    "Assault Peace Officer": 1.2,
    "Assault Peace Officer Wpn/Cbh": 2.0,
    "Assault - Resist/ Prevent Seiz": 1.0,
    "Assault - Force/Thrt/Impede": 1.0,
    "Discharge Firearm With Intent": 4.0,
    "Discharge Firearm - Recklessly": 3.5,
    "Pointing A Firearm": 3.0,
    "Use Firearm / Immit Commit Off": 3.5,
    "Administering Noxious Thing": 2.0,
    "Crim Negligence Bodily Harm": 2.5,
    "Disarming Peace/Public Officer": 2.0,
    "Theft Of Motor Vehicle": 1.0,
    "B&E": 1.5,
    "B&E W'Intent": 1.8,
    "B&E Out": 1.2,
    "Unlawfully In Dwelling-House": 2.0,
    "Robbery - Mugging": 2.0,
    "Robbery With Weapon": 3.0,
    "Robbery - Other": 2.0,
    "Robbery - Business": 1.8,
    "Robbery - Home Invasion": 3.5,
    "Robbery - Vehicle Jacking": 3.0,
    "Robbery - Swarming": 2.2,
    "Robbery - Purse Snatch": 1.5,
    "Robbery - Financial Institute": 2.0,
    "Robbery - Delivery Person": 1.8,
    "Robbery - Taxi": 1.8,
    "Robbery - Atm": 2.0,
    "Robbery - Armoured Car": 2.0,
    "Theft Over": 1.0,
    "Theft From Motor Vehicle Over": 0.8,
    "Theft Over - Shoplifting": 0.6,
    "Theft From Mail / Bag / Key": 0.8,
    "Theft Over - Distraction": 1.0,
    "Theft Over - Bicycle": 0.6,
    "Theft - Misapprop Funds Over": 0.6,
}

CATEGORY_DEFAULT_WEIGHTS: dict[str, float] = {
    "Assault": 1.0,
    "Auto Theft": 1.0,
    "Break and Enter": 1.5,
    "Robbery": 2.0,
    "Theft Over": 1.0,
}

GRADE_COLORS = {
    "Safer than average": "#2e7d32",
    "About average": "#fbc02d",
    "Less safe than average": "#e53935",
}


def _weight_for(offence: str, category: str) -> float:
    if offence in OFFENCE_WEIGHTS:
        return OFFENCE_WEIGHTS[offence]
    return CATEGORY_DEFAULT_WEIGHTS.get(category, 1.0)


@dataclass
class SafetyResult:
    local_incident_count: int
    local_weighted_count: float
    citywide_weighted_count: float
    expected_weighted_count: float  # citywide rate scaled to the local catchment's area
    ratio: float                    # local_weighted_count / expected_weighted_count
    grade: str
    category_breakdown: dict[str, int] = field(default_factory=dict)
    radius_m: int = SEARCH_RADIUS_M
    window_days: int = WINDOW_DAYS


def _date_where_clause() -> str:
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    return f"REPORT_DATE >= TIMESTAMP '{since.strftime('%Y-%m-%d %H:%M:%S')}'"


def query_local_incidents(lat: float, lon: float, radius_m: int = SEARCH_RADIUS_M) -> list[dict]:
    """Return raw incident records (CSI_CATEGORY, OFFENCE) within radius_m of
    (lat, lon) reported in the last WINDOW_DAYS days."""
    params = {
        "where": _date_where_clause(),
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "distance": radius_m,
        "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CSI_CATEGORY,OFFENCE",
        "resultRecordCount": 2000,
        "f": "json",
    }
    resp = requests.get(CSI_FEATURESERVER_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Crime data service error: {data['error']}")
    return [f["attributes"] for f in data.get("features", [])]


def query_citywide_weighted_total() -> float:
    """Citywide weighted incident total over the same WINDOW_DAYS window, via
    a single aggregate query (grouped by CSI_CATEGORY/OFFENCE counts, not one
    row per incident)."""
    params = {
        "where": _date_where_clause(),
        "outFields": "CSI_CATEGORY,OFFENCE",
        "groupByFieldsForStatistics": "CSI_CATEGORY,OFFENCE",
        "outStatistics": (
            '[{"statisticType":"count","onStatisticField":"OBJECTID","outStatisticFieldName":"cnt"}]'
        ),
        "f": "json",
    }
    resp = requests.get(CSI_FEATURESERVER_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Crime data service error: {data['error']}")

    total = 0.0
    for feature in data.get("features", []):
        attrs = feature["attributes"]
        weight = _weight_for(attrs.get("OFFENCE") or "", attrs.get("CSI_CATEGORY") or "")
        total += weight * attrs["cnt"]
    return total


def _grade(ratio: float) -> str:
    if ratio < 0.8:
        return "Safer than average"
    if ratio > 1.2:
        return "Less safe than average"
    return "About average"


def score_safety(lat: float, lon: float, citywide_weighted_total: float, radius_m: int = SEARCH_RADIUS_M) -> SafetyResult:
    incidents = query_local_incidents(lat, lon, radius_m)

    local_weighted = 0.0
    breakdown: Counter = Counter()
    for row in incidents:
        category = row.get("CSI_CATEGORY") or "Unknown"
        offence = row.get("OFFENCE") or "Unknown"
        local_weighted += _weight_for(offence, category)
        breakdown[category] += 1

    local_area_km2 = math.pi * (radius_m / 1000) ** 2
    expected = citywide_weighted_total * (local_area_km2 / TORONTO_LAND_AREA_KM2)
    ratio = (local_weighted / expected) if expected > 0 else 0.0

    return SafetyResult(
        local_incident_count=len(incidents),
        local_weighted_count=round(local_weighted, 1),
        citywide_weighted_count=round(citywide_weighted_total, 1),
        expected_weighted_count=round(expected, 1),
        ratio=round(ratio, 2),
        grade=_grade(ratio),
        category_breakdown=dict(breakdown),
        radius_m=radius_m,
    )


if __name__ == "__main__":
    from geocode import geocode_address

    citywide_total = query_citywide_weighted_total()
    print(f"Citywide weighted incident total (last {WINDOW_DAYS} days): {citywide_total:.1f}")

    for address in ("100 Queen St W", "35 Playter Blvd", "25 Rathburn Rd W, Etobicoke"):
        lat, lon = geocode_address(address)
        result = score_safety(lat, lon, citywide_total)
        print(f"\n=== {address} ===")
        print(f"  {result.grade} — {result.local_incident_count} incidents, "
              f"weighted {result.local_weighted_count} vs expected {result.expected_weighted_count} "
              f"(ratio {result.ratio})")
        print(f"  breakdown: {result.category_breakdown}")
