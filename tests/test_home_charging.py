import pytest

from common import buildings
from conftest import load_app_module
from overpass_fixtures import at, way

home_charging = load_app_module("ev-scorecard", "home_charging")


@pytest.fixture
def overpass(monkeypatch):
    """Serve the given elements as the Overpass response for any query."""
    def _serve(*elements):
        monkeypatch.setattr(
            home_charging, "fetch_building",
            lambda lat, lon, ua: buildings.pick_building(list(elements), lat, lon),
        )
    return _serve


def _check(x=0, y=0):
    return home_charging.check_home_charging(*at(x, y))


def test_house_containing_point_is_feasible_high(overpass):
    overpass(way(-8, -8, 8, 8, building="house"))
    result = _check()
    assert (result.feasible, result.confidence) == (True, "high")


def test_nearest_but_not_containing_lowers_confidence(overpass):
    overpass(way(5, 5, 20, 20, building="house"))
    result = _check()
    assert (result.feasible, result.confidence) == (True, "medium")
    assert "nearest mapped building" in result.note


def test_residential_is_low_confidence_not_a_confident_no(overpass):
    # building=residential covers bungalows to towers; it used to be read
    # as a high-confidence "multi-unit, no private parking".
    overpass(way(-8, -8, 8, 8, building="residential"))
    result = _check()
    assert (result.feasible, result.confidence) == (False, "low")


def test_tall_generic_building_is_confident_no(overpass):
    overpass(way(-20, -20, 20, 20, **{"building": "yes", "building:levels": "20"}))
    result = _check()
    assert (result.feasible, result.confidence) == (False, "high")
    assert result.dwelling_type == "yes (20 storeys)"


def test_no_building(overpass):
    overpass()
    result = _check()
    assert (result.feasible, result.dwelling_type) == (False, "unknown")
