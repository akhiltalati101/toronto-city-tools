import math

import pandas as pd
import pytest

from common import buildings
from conftest import load_app_module
from overpass_fixtures import at, way

rental = load_app_module("area-scorecard", "rental")


def _row(site, x=None, y=None, score=75, evaluated="2025-06-01", **extra):
    lat, lon = at(x, y) if x is not None else (math.nan, math.nan)
    return {
        "SITE ADDRESS": site, "LATITUDE": lat, "LONGITUDE": lon,
        "CURRENT BUILDING EVAL SCORE": score, "EVALUATION COMPLETED ON": evaluated,
        "CONFIRMED STOREYS": 20, "CONFIRMED UNITS": 200, "PROPERTY TYPE": "PRIVATE",
        "ELEVATOR MAINTENANCE": 1, "SECURITY": 3, "INTERCOM": "N/A",
        **extra,
    }


def _df(*rows):
    return pd.DataFrame(list(rows))


@pytest.fixture
def overpass(monkeypatch):
    """Serve the given elements as the Overpass response; serve(None) simulates an outage."""
    def _serve(*elements):
        def fake_fetch(lat, lon, ua):
            if elements == (None,):
                raise ValueError("Building lookup service (Overpass) is unavailable right now")
            return buildings.pick_building(list(elements), lat, lon)
        monkeypatch.setattr(rental.buildings, "fetch_building", fake_fetch)
    return _serve


def _check(df, address="50 Example St", x=0, y=0):
    return rental.check_rental(*at(x, y), address, df)


def test_generic_tower_with_rentsafe_point_inside_is_matched(overpass):
    # The original bug: most towers are tagged building=yes with no levels,
    # which used to short-circuit before RentSafeTO was ever consulted.
    overpass(way(-20, -20, 20, 20, building="yes"))
    result = _check(_df(_row("50 EXAMPLE ST", x=12, y=-15)), address="50 Example Street")
    assert result.rentsafe is not None
    assert result.rentsafe.address == "50 EXAMPLE ST"
    assert result.building.status == rental.APARTMENT
    assert result.facebook_search_url is None


def test_rentsafe_point_just_outside_footprint_still_matches(overpass):
    # RentSafeTO coordinates often sit on the frontage, a few metres out.
    overpass(way(-20, -20, 20, 20, building="yes"))
    result = _check(_df(_row("99 OTHER ST", x=0, y=-28)))
    assert result.rentsafe.address == "99 OTHER ST"


def test_house_next_to_tower_does_not_inherit_its_score(overpass):
    # House tagged building=yes (as many Toronto houses are); a RentSafeTO
    # tower 40 m away is within the old 60 m radius but outside the house.
    overpass(way(-6, -6, 6, 6, building="yes"), way(25, -30, 80, 30, building="apartments"))
    result = _check(_df(_row("200 TOWER RD", x=45, y=0)))
    assert result.rentsafe is None
    assert result.building.status == rental.UNKNOWN
    assert result.facebook_search_url is not None


def test_house_tag_is_not_apartment_without_facebook_link(overpass):
    overpass(way(-6, -6, 6, 6, building="house"))
    result = _check(_df(_row("200 TOWER RD", x=500, y=500)))
    assert result.building.status == rental.NOT_APARTMENT
    assert result.facebook_search_url is None


def test_unmatched_apartment_is_probably_a_condo(overpass):
    overpass(way(-20, -20, 20, 20, building="apartments"))
    result = _check(_df(_row("200 TOWER RD", x=500, y=500)))
    assert result.building.status == rental.APARTMENT
    assert result.rentsafe is None
    assert result.facebook_search_url is not None


def test_residential_tag_is_unknown_not_apartment(overpass):
    overpass(way(-6, -6, 6, 6, building="residential"))
    assert _check(_df(_row("200 TOWER RD", x=500, y=500))).building.status == rental.UNKNOWN


def test_overpass_outage_degrades_to_radius_match(overpass):
    overpass(None)
    result = _check(_df(_row("FAR AWAY", x=55, y=55), _row("CLOSE BY", x=20, y=10)))
    assert result.rentsafe.address == "CLOSE BY"


def test_overpass_outage_without_match_is_unknown(overpass):
    overpass(None)
    result = _check(_df(_row("200 TOWER RD", x=500, y=500)))
    assert result.building.status == rental.UNKNOWN
    assert "didn't respond" in result.building.note


def test_radius_fallback_picks_nearest_not_first_row(overpass):
    # No building found: the old code took iloc[0] of everything in range.
    overpass()
    result = _check(_df(_row("A", x=50, y=0), _row("B", x=10, y=0), _row("C", x=-40, y=0)))
    assert result.rentsafe.address == "B"


def test_address_match_uses_distance_to_pick_east_or_west(overpass):
    overpass()
    df = _df(_row("100 QUEEN ST E", x=3000, y=0), _row("100 QUEEN ST W", x=150, y=100))
    result = _check(df, address="100 Queen St W, Toronto")
    assert result.rentsafe.address == "100 QUEEN ST W"
    # Typed without a direction, the nearer one wins.
    assert _check(df, address="100 Queen Street").rentsafe.address == "100 QUEEN ST W"


def test_address_match_finds_rows_without_coordinates(overpass):
    overpass(way(-6, -6, 6, 6, building="yes"))
    result = _check(_df(_row("50 EXAMPLE ST")), address="50 Example Street")
    assert result.rentsafe.address == "50 EXAMPLE ST"


def test_latest_evaluation_and_lowest_categories(overpass):
    overpass(way(-20, -20, 20, 20, building="yes"))
    df = _df(
        _row("50 EXAMPLE ST", x=0, y=0, score=60, evaluated="2024-01-10"),
        _row("50 EXAMPLE ST", x=0, y=0, score=88, evaluated="2025-11-02"),
    )
    match = _check(df).rentsafe
    assert (match.overall_score, match.evaluated_on) == (88, "2025-11-02")
    assert match.lowest_categories == [("Elevator Maintenance", 1), ("Security", 3)]
