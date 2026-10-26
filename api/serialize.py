"""Converts pipeline results (dataclasses holding shapely geometries,
GeoDataFrames and numpy scalars) into the JSON-safe response models in
schemas.py. NaN never reaches the response: JSON has no NaN, and the
parquet datasets use it for missing names, pricing, etc."""
from __future__ import annotations

import math
from typing import Any, Optional

import geopandas as gpd
from shapely.geometry import mapping

from api import schemas
from toronto_tools.area.pipeline import AreaScorecard
from toronto_tools.area.zoning import SEARCH_RADIUS_M as ZONING_RADIUS_M
from toronto_tools.city.pipeline import ScorecardResult as CityResult
from toronto_tools.ev.charger_access import parse_connector_types
from toronto_tools.ev.pipeline import ScorecardResult as EvResult


def _clean(value: Any) -> Any:
    """numpy scalar -> Python scalar; NaN/None/"" -> None."""
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _int(value: Any) -> int:
    value = _clean(value)
    return int(value) if value is not None else 0


def _geometry(geom) -> dict:
    return mapping(geom)


def _point_features(gdf: gpd.GeoDataFrame, properties) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.geometry.x, row.geometry.y]},
                "properties": properties(row),
            }
            for _, row in gdf.iterrows()
        ],
    }


def city(card: CityResult) -> schemas.CityScore:
    result = card.result
    features = []
    for category, gdf in card.amenities.items():
        features += _point_features(
            gdf, lambda row, category=category: {"category": category, "name": _clean(row.get("name"))}
        )["features"]

    return schemas.CityScore(
        address=card.address, lat=card.lat, lon=card.lon,
        overall=float(result.overall),
        grade=result.grade,
        weights=result.weights,
        breakdown={
            cat: schemas.CategoryScore(
                proximity=float(s.proximity), variety=float(s.variety), combined=float(s.combined),
                count=s.count, nearest_min=_clean(s.nearest_min),
            )
            for cat, s in result.breakdown.items()
        },
        walk_isochrone=_geometry(card.walk_polygon),
        bike_isochrone=_geometry(card.bike_polygon),
        amenities={"type": "FeatureCollection", "features": features},
    )


def _charger_properties(row) -> dict:
    return {
        "address": _clean(row.get("address")),
        "network": _clean(row.get("network")),
        "access_code": _clean(row.get("access_code")) or "unknown",
        "connectors": sorted(parse_connector_types(row.get("connector_types"))),
        "level2_ports": _int(row.get("level2_ports")),
        "level3_ports": _int(row.get("level3_ports")),
        "total_ports": _int(row.get("total_ports")),
        "pricing": _clean(row.get("pricing")),
        "access_hours": _clean(row.get("access_hours")),
        "walk_sec": _clean(row.get("walk_sec")),
    }


def ev(card: EvResult) -> schemas.EvScore:
    access = card.charger_access
    return schemas.EvScore(
        address=card.address, lat=card.lat, lon=card.lon,
        home_charging=schemas.HomeCharging(**vars(card.home_charging)),
        public_access=schemas.ChargerAccess(
            combined=float(access.combined), proximity=float(access.proximity), variety=float(access.variety),
            count=access.count, nearest_min=_clean(access.nearest_min), grade=access.grade,
        ),
        isochrone=_geometry(card.isochrone_polygon),
        chargers=_point_features(card.nearby_chargers, _charger_properties),
    )


def _optional_int(value: Any) -> Optional[int]:
    value = _clean(value)
    return int(value) if value is not None else None


def area(card: AreaScorecard) -> schemas.AreaScore:
    rental = card.rental
    rentsafe = None
    if rental.rentsafe is not None:
        r = rental.rentsafe
        rentsafe = schemas.RentSafe(
            address=r.address,
            overall_score=_optional_int(r.overall_score),
            evaluated_on=_clean(r.evaluated_on),
            storeys=_optional_int(r.storeys),
            units=_optional_int(r.units),
            property_type=_clean(r.property_type),
            lowest_categories=[
                schemas.InspectionCategory(category=c, score=s) for c, s in r.lowest_categories
            ],
        )

    return schemas.AreaScore(
        address=card.address, lat=card.lat, lon=card.lon,
        safety=schemas.Safety(**vars(card.safety)),
        rental=schemas.Rental(
            building=schemas.RentalBuilding(
                status=rental.building.status,
                dwelling_type=rental.building.dwelling_type,
                note=rental.building.note,
            ),
            rentsafe=rentsafe,
            facebook_search_url=rental.facebook_search_url,
        ),
        zoning=[
            schemas.ZoningApplication(
                **vars(zd.application), summary=zd.summary, display_text=zd.display_text,
            )
            for zd in card.zoning_applications
        ],
        zoning_radius_m=ZONING_RADIUS_M,
    )
