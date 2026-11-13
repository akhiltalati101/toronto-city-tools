"""Response models for the API. Geometry fields are plain GeoJSON dicts
(geometry objects or FeatureCollections) so the frontend can hand them
straight to the map."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

GeoJSON = dict[str, Any]


class Location(BaseModel):
    address: str
    lat: float
    lon: float


# --- City -------------------------------------------------------------------

class CategoryScore(BaseModel):
    proximity: float
    variety: float
    combined: float
    count: int
    nearest_min: Optional[float]


class CityScore(Location):
    overall: float
    grade: str
    weights: dict[str, float]
    breakdown: dict[str, CategoryScore]
    walk_isochrone: GeoJSON
    bike_isochrone: GeoJSON
    amenities: GeoJSON   # FeatureCollection; properties: category, name


# --- EV ---------------------------------------------------------------------

class HomeCharging(BaseModel):
    feasible: bool
    confidence: str
    dwelling_type: str
    note: str


class ChargerAccess(BaseModel):
    combined: float
    proximity: float
    variety: float
    count: int
    nearest_min: Optional[float]
    grade: str


class EvScore(Location):
    home_charging: HomeCharging
    # Every public charger in the walk isochrone, before any connector
    # filter. The frontend re-scores per connector selection from the
    # chargers' walk_sec values (see charger_access.score_from_walk_times).
    public_access: ChargerAccess
    isochrone: GeoJSON
    # FeatureCollection; properties: address, network, access_code,
    # connectors (list of codes), level2_ports, level3_ports, total_ports,
    # pricing, access_hours, walk_sec (null if unreachable).
    chargers: GeoJSON


# --- Area -------------------------------------------------------------------

class Safety(BaseModel):
    local_incident_count: int
    local_weighted_count: float
    citywide_weighted_count: float
    expected_weighted_count: float
    ratio: float
    grade: str
    category_breakdown: dict[str, int]
    radius_m: int
    window_days: int


class RentalBuilding(BaseModel):
    status: str          # "apartment" | "not_apartment" | "unknown"
    dwelling_type: str
    note: str


class InspectionCategory(BaseModel):
    category: str
    score: int           # 1 (worst) to 3 (best)


class RentSafe(BaseModel):
    address: str
    overall_score: Optional[int]
    evaluated_on: Optional[str]
    storeys: Optional[int]
    units: Optional[int]
    property_type: Optional[str]
    lowest_categories: list[InspectionCategory]


class Rental(BaseModel):
    building: RentalBuilding
    rentsafe: Optional[RentSafe]
    facebook_search_url: Optional[str]


class ZoningApplication(BaseModel):
    application_number: str
    address: str
    application_type: str
    folder_type: str
    status: str
    description: Optional[str]
    summary: Optional[str]
    display_text: str
    intake_date_ms: Optional[int]
    hearing_date_ms: Optional[int]
    aic_url: Optional[str]
    lat: float
    lon: float
    is_major: bool


class AreaScore(Location):
    safety: Safety
    rental: Rental
    zoning: list[ZoningApplication]
    zoning_radius_m: int
