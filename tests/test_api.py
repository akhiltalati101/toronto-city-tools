"""API tests against a synthetic street grid and tiny datasets, with every
live service (Photon, Overpass, Toronto Police, AIC, RentSafeTO) stubbed."""
import math
import os

import geopandas as gpd
import pytest
from shapely.geometry import Point

os.environ["PRELOAD_DATA"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402
from graph_fixtures import grid  # noqa: E402
from overpass_fixtures import ORIGIN_LAT, ORIGIN_LON, at  # noqa: E402
from toronto_tools.area import pipeline as area_pipeline  # noqa: E402
from toronto_tools.area import safety  # noqa: E402
from toronto_tools.area.rental import APARTMENT, BuildingClass, RentalResult, RentSafeToScore  # noqa: E402
from toronto_tools.area.zoning import ZoningApplication  # noqa: E402
from toronto_tools.city import amenities, pipeline as city_pipeline  # noqa: E402
from toronto_tools.common import geocode  # noqa: E402
from toronto_tools.ev import pipeline as ev_pipeline  # noqa: E402
from toronto_tools.ev.home_charging import HomeChargingResult  # noqa: E402


def _points(rows):
    return gpd.GeoDataFrame(
        [{k: v for k, v in r.items() if k != "xy"} for r in rows],
        geometry=[Point(at(*r["xy"])[1], at(*r["xy"])[0]) for r in rows],
        crs="EPSG:4326",
    )


@pytest.fixture
def client(monkeypatch):
    G = grid()
    monkeypatch.setattr(city_pipeline, "get_city_graph", lambda network_type: G)
    monkeypatch.setattr(amenities, "get_city_amenities", lambda: _points([
        {"xy": (40, 40), "category": "grocery", "name": "Corner Store"},
        {"xy": (-200, 80), "category": "grocery", "name": math.nan},
        {"xy": (100, -100), "category": "parks", "name": "Little Park"},
        {"xy": (9000, 9000), "category": "parks", "name": "Far Park"},  # outside the isochrone
    ]))
    monkeypatch.setattr(ev_pipeline, "get_walk_graph", lambda: G)
    monkeypatch.setattr(ev_pipeline, "get_charging_stations", lambda: _points([
        {"xy": (60, 0), "address": "1 Plug St", "network": "FLO", "access_code": "public",
         "connector_types": "J1772, J1772COMBO", "level2_ports": 2, "level3_ports": 1, "total_ports": 3,
         "pricing": math.nan, "access_hours": "24 hours daily"},
        {"xy": (-300, 200), "address": "2 Tesla Ave", "network": "Tesla", "access_code": "public",
         "connector_types": "TESLA", "level2_ports": 0, "level3_ports": 8, "total_ports": 8,
         "pricing": "$0.50/kWh", "access_hours": "Not listed"},
        {"xy": (0, -150), "address": "3 Condo Rd", "network": "Non-Networked", "access_code": "private",
         "connector_types": "Not listed", "level2_ports": 1, "level3_ports": 0, "total_ports": 1,
         "pricing": math.nan, "access_hours": math.nan},
    ]))
    monkeypatch.setattr(ev_pipeline, "check_home_charging", lambda lat, lon: HomeChargingResult(
        feasible=True, confidence="high", dwelling_type="house", note="Detached house."))
    monkeypatch.setattr(geocode, "geocode_address", lambda address: (ORIGIN_LAT, ORIGIN_LON))
    main.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_config_exposes_profiles(client):
    profiles = client.get("/api/config").json()["profiles"]
    assert set(profiles) == {"General", "Family", "Senior", "Car-Free", "Student"}


def test_city_score_by_address(client):
    resp = client.get("/api/city/score", params={"address": "100 Queen St W"})
    assert resp.status_code == 200
    body = resp.json()
    assert (body["address"], body["lat"], body["lon"]) == ("100 Queen St W", ORIGIN_LAT, ORIGIN_LON)
    assert body["breakdown"]["grocery"]["count"] == 2
    assert body["breakdown"]["parks"]["count"] == 1
    assert body["breakdown"]["schools"]["count"] == 0
    assert body["breakdown"]["schools"]["nearest_min"] is None
    assert body["walk_isochrone"]["type"] == "Polygon"
    assert body["bike_isochrone"]["type"] == "Polygon"
    names = sorted(str(f["properties"]["name"]) for f in body["amenities"]["features"])
    assert names == ["Corner Store", "Little Park", "None"]  # NaN name -> null


def test_city_score_by_point_skips_geocoding(client, monkeypatch):
    def _no_geocoding(address):
        raise AssertionError("should not geocode")
    monkeypatch.setattr(geocode, "geocode_address", _no_geocoding)
    lat, lon = at(20, 20)
    body = client.get("/api/city/score", params={"lat": lat, "lon": lon}).json()
    assert body["address"] == f"{lat:.5f}, {lon:.5f}"


def test_city_profile_changes_overall_not_breakdown(client):
    general = client.get("/api/city/score", params={"address": "x"}).json()
    family = client.get("/api/city/score", params={"address": "x", "profile": "Family"}).json()
    assert general["breakdown"] == family["breakdown"]
    assert family["weights"]["schools"] == 0.25


def test_validation_errors_are_400s(client):
    resp = client.get("/api/city/score", params={"lat": 45.42, "lon": -75.69})
    assert resp.status_code == 400
    assert "outside" in resp.json()["detail"]
    assert client.get("/api/city/score").status_code == 400
    assert client.get("/api/city/score", params={"address": "x", "profile": "Nope"}).status_code == 400


def test_ev_score(client):
    body = client.get("/api/ev/score", params={"address": "x"}).json()
    assert body["home_charging"]["dwelling_type"] == "house"
    chargers = {f["properties"]["address"]: f["properties"] for f in body["chargers"]["features"]}
    assert set(chargers) == {"1 Plug St", "2 Tesla Ave", "3 Condo Rd"}
    assert chargers["1 Plug St"]["connectors"] == ["J1772", "J1772COMBO"]
    assert chargers["1 Plug St"]["pricing"] is None
    assert chargers["3 Condo Rd"]["connectors"] == []
    assert all(c["walk_sec"] > 0 for c in chargers.values())
    # Private stations are shown but not scored.
    assert body["public_access"]["count"] == 2
    assert body["isochrone"]["type"] == "Polygon"


@pytest.fixture
def area_stubs(monkeypatch):
    monkeypatch.setattr(area_pipeline, "query_nearby_applications", lambda lat, lon: [
        ZoningApplication("24 123456 STE 10 OZ", "10 Main St", "Community planning", "OPA / Rezoning",
                          "Under Review", "Proposed 30-storey tower", 1700000000000, None,
                          "https://example.com/aic", *at(50, 50), True),
        ZoningApplication("A0001/24TEY", "12 Main St", "C of A", "Minor Variance",
                          "Hearing Scheduled", None, None, None, None, *at(-30, 10), False),
    ])
    monkeypatch.setattr(area_pipeline, "get_zoning_summaries", lambda: {
        "24 123456 STE 10 OZ": {"summary": "A 30-storey condo tower."}})
    monkeypatch.setattr(area_pipeline, "_cached_citywide_weighted_total", lambda: 10000.0)
    monkeypatch.setattr(safety, "query_local_incidents", lambda lat, lon, radius_m: [
        {"CSI_CATEGORY": "Assault", "OFFENCE": "Assault"},
        {"CSI_CATEGORY": "Auto Theft", "OFFENCE": "Theft Of Motor Vehicle"},
    ])
    monkeypatch.setattr(area_pipeline, "get_rentsafe_data", lambda: None)
    monkeypatch.setattr(area_pipeline, "check_rental", lambda lat, lon, address, df: RentalResult(
        building=BuildingClass(APARTMENT, "apartments", "Registered with RentSafeTO."),
        rentsafe=RentSafeToScore("10 MAIN ST", 88, "2025-06-01", 12, 140, "PRIVATE", [("Security", 2)]),
        facebook_search_url=None,
    ))


def test_area_score(client, area_stubs):
    body = client.get("/api/area/score", params={"address": "x"}).json()
    assert body["safety"]["local_incident_count"] == 2
    assert body["safety"]["category_breakdown"] == {"Assault": 1, "Auto Theft": 1}
    assert body["rental"]["rentsafe"]["overall_score"] == 88
    assert body["rental"]["rentsafe"]["lowest_categories"] == [{"category": "Security", "score": 2}]
    major, minor = body["zoning"]
    assert (major["summary"], major["display_text"]) == ("A 30-storey condo tower.", "A 30-storey condo tower.")
    assert minor["summary"] is None
    assert minor["display_text"].startswith("No description provided")
    assert body["zoning_radius_m"] == 400


def test_upstream_failure_is_a_502(client, area_stubs, monkeypatch):
    import requests

    def _down(lat, lon, radius_m):
        raise requests.exceptions.ConnectionError("boom")
    monkeypatch.setattr(safety, "query_local_incidents", _down)
    resp = client.get("/api/area/score", params={"address": "x"})
    assert resp.status_code == 502
    assert "boom" not in resp.json()["detail"]


def test_rate_limit(client):
    # Default RATE_LIMIT is 20/minute; rejected requests count too.
    codes = [client.get("/api/city/score", params={"lat": 0, "lon": 0}).status_code for _ in range(25)]
    assert codes[:20] == [400] * 20
    assert codes[20:] == [429] * 5


def test_cors_allows_configured_origin(client):
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    resp = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
