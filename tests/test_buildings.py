import pytest
import requests

from common import buildings
from overpass_fixtures import at, split_relation, way


def _pick(elements, x=0, y=0):
    lat, lon = at(x, y)
    return buildings.pick_building(elements, lat, lon)


def test_prefers_containing_footprint_over_nearer_centroid():
    # Long slab (centroid 50 m east) contains the point at its west end; a
    # small house next door has its centroid only ~12 m away. Centroid
    # distance picked the house; containment must pick the slab.
    slab = way(-5, -10, 105, 10, building="apartments")
    house = way(-20, 2, -8, 14, building="house")
    picked = _pick([house, slab])
    assert picked.building_type == "apartments"
    assert picked.contains_point


def test_falls_back_to_nearest_edge_when_nothing_contains_point():
    # Point on the street: the big building's edge is 6 m away, but the
    # small building's centroid is closer than the big one's.
    big = way(-50, 6, 50, 60, building="apartments")
    small = way(-14, -20, -6, -12, building="house")
    picked = _pick([small, big])
    assert picked.building_type == "apartments"
    assert not picked.contains_point


def test_nested_footprints_pick_the_smallest():
    outer = way(-50, -50, 50, 50, building="yes")
    inner = way(-5, -5, 5, 5, building="apartments")
    assert _pick([outer, inner]).building_type == "apartments"


def test_relation_with_split_outer_ring():
    picked = _pick([split_relation(-30, -30, 30, 30, building="residential")])
    assert picked.building_type == "residential"
    assert picked.contains_point


def test_no_usable_geometry_returns_none():
    assert _pick([]) is None
    assert _pick([{"type": "way", "tags": {"building": "yes"}, "geometry": []}]) is None


@pytest.mark.parametrize("tags, kind", [
    ({"building": "yes"}, buildings.UNKNOWN),
    ({"building": "residential"}, buildings.UNKNOWN),
    ({}, buildings.UNKNOWN),
    ({"building": "apartments"}, buildings.MULTI_UNIT),
    ({"building": "yes", "building:levels": "12"}, buildings.MULTI_UNIT),
    ({"building": "residential", "building:levels": "4"}, buildings.MULTI_UNIT),
    ({"building": "residential", "building:levels": "2"}, buildings.UNKNOWN),
    ({"building": "commercial", "building:levels": "10"}, buildings.NON_RESIDENTIAL),
    ({"building": "house"}, buildings.HOUSE),
    ({"building": "semidetached_house"}, buildings.HOUSE),
    ({"building": "terrace"}, buildings.TOWNHOUSE),
    ({"building": "house", "building:levels": "two"}, buildings.HOUSE),
])
def test_classify(tags, kind):
    assert buildings.classify(buildings.Building(tags=tags, footprint=None, contains_point=True)).kind == kind


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_building_sends_user_agent_and_parses(monkeypatch):
    calls = []

    def fake_post(url, data, headers, timeout):
        calls.append(headers)
        return _Resp({"elements": [way(-10, -10, 10, 10, building="house")]})

    monkeypatch.setattr(buildings.requests, "post", fake_post)
    lat, lon = at(0, 0)
    assert buildings.fetch_building(lat, lon, "test-agent").building_type == "house"
    assert calls == [{"User-Agent": "test-agent"}]


def test_fetch_building_retries_then_raises_value_error(monkeypatch):
    attempts = []

    def failing_post(*args, **kwargs):
        attempts.append(1)
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(buildings.requests, "post", failing_post)
    with pytest.raises(ValueError, match="Overpass"):
        buildings.fetch_building(43.65, -79.38, "test-agent")
    assert len(attempts) == 3
