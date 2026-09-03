"""Live lookup of nearby zoning/development applications — the "what's
coming to this neighbourhood" feature.

Queries the public ArcGIS layer behind the City of Toronto's Application
Information Centre (AIC) map directly, per request, rather than needing a
prebuilt dataset: the layer supports a point+radius spatial query and the
result set for any single address is small (a handful to a few dozen
applications), so there's no benefit to pre-fetching it citywide the way
ev-scorecard pre-fetches chargers. This also keeps "coming soon" genuinely
current — there's no pipeline lag between an application appearing in the
city's system and it showing up here.

Plain-English summaries of each application's FOLDERDESCRIPTION are looked
up separately (see data.py) from a periodically-rebuilt cache — this module
only returns the raw application data.
"""
from dataclasses import dataclass
from typing import Optional

import requests

AIC_FEATURESERVER_URL = (
    "https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/FeatureServer/60/query"
)

# Applications more than this far from the address aren't "in the
# neighbourhood" in any useful sense for a resident deciding whether to move
# somewhere — chosen to roughly match a short walk, same spirit as the
# 15-minute walk catchments used elsewhere in this repo family, but as a
# straight-line radius since this is a simple proximity query, not a
# walkability score.
SEARCH_RADIUS_M = 400

# Only "Open" applications are still active/undecided — "coming soon" means
# something that hasn't already been fully resolved one way or the other.
# Some very old records sit in "Open" indefinitely (a data-quality quirk of
# the source system, confirmed by spot-checking the live API), so results
# are also capped and sorted by intake date to keep genuinely stale entries
# from crowding out recent ones.
MAX_RESULTS = 25

# Folder types that represent visible neighbourhood-scale change (new
# buildings, road/site work) vs. routine property-level paperwork (a
# homeowner's setback variance). Surfaced as `is_major` so the UI/map can
# visually distinguish "new condo tower" from "someone's deck permit"
# without hiding the latter entirely.
MAJOR_APPLICATION_TYPES = {"Community planning", "TLAB"}


@dataclass
class ZoningApplication:
    application_number: str
    address: str
    application_type: str        # e.g. "Community planning", "C of A", "TLAB"
    folder_type: str             # e.g. "OPA / Rezoning", "Site Plan Approval", "Minor Variance"
    status: str                  # STATUS_DESC, e.g. "Under Review"
    description: Optional[str]   # raw city text (FOLDERDESCRIPTION), may be None
    intake_date_ms: Optional[int]
    hearing_date_ms: Optional[int]
    aic_url: Optional[str]
    lat: float
    lon: float
    is_major: bool


def _to_application(attrs: dict, geom: Optional[dict]) -> Optional[ZoningApplication]:
    lat = attrs.get("LATITUDE")
    lon = attrs.get("LONGITUDE")
    if lat is None or lon is None:
        if geom:
            lon, lat = geom.get("x"), geom.get("y")
    if lat is None or lon is None:
        return None

    app_type = attrs.get("APPLICATION_TYPE") or "Unknown"
    return ZoningApplication(
        application_number=attrs.get("APPLICATION_NUMBER") or "",
        address=(attrs.get("FULL_ADDRESS") or "").strip(),
        application_type=app_type,
        folder_type=attrs.get("FOLDERTYPE_DESC") or "Unknown",
        status=attrs.get("STATUS_DESC") or attrs.get("STATUS_GROUP") or "Unknown",
        description=attrs.get("FOLDERDESCRIPTION"),
        intake_date_ms=attrs.get("INDATE"),
        hearing_date_ms=attrs.get("HEARING_DATE"),
        aic_url=attrs.get("AIC_URL"),
        lat=lat,
        lon=lon,
        is_major=app_type in MAJOR_APPLICATION_TYPES,
    )


def query_nearby_applications(lat: float, lon: float, radius_m: int = SEARCH_RADIUS_M) -> list[ZoningApplication]:
    """Return open zoning/development applications within radius_m of (lat, lon),
    nearest-intake-date first, deduplicated by application_number (multi-parcel
    applications repeat one row per address in the source layer).
    """
    params = {
        "where": "STATUS_GROUP='Open'",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "distance": radius_m,
        "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": (
            "APPLICATION_NUMBER,FULL_ADDRESS,APPLICATION_TYPE,FOLDERTYPE_DESC,"
            "STATUS_DESC,STATUS_GROUP,FOLDERDESCRIPTION,INDATE,HEARING_DATE,"
            "AIC_URL,LATITUDE,LONGITUDE"
        ),
        "orderByFields": "INDATE DESC",
        "resultRecordCount": MAX_RESULTS,
        "outSR": 4326,
        "f": "geojson",
    }

    resp = requests.get(AIC_FEATURESERVER_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"AIC service error: {data['error']}")

    seen: set[str] = set()
    results: list[ZoningApplication] = []
    for feature in data.get("features", []):
        app = _to_application(feature.get("properties", {}), feature.get("geometry"))
        if app is None:
            continue
        key = app.application_number or f"{app.address}|{app.folder_type}"
        if key in seen:
            continue
        seen.add(key)
        results.append(app)

    return results


if __name__ == "__main__":
    from geocode import geocode_address

    for address in ("100 Queen St W", "208 Bloor St W", "35 Playter Blvd"):
        lat, lon = geocode_address(address)
        apps = query_nearby_applications(lat, lon)
        print(f"\n=== {address} ({len(apps)} nearby open applications) ===")
        for app in apps[:5]:
            desc = (app.description or "(no description)")[:80]
            print(f"  [{app.folder_type}] {app.address} — {app.status} — {desc}")
