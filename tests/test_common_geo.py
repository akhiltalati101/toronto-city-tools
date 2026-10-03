from types import SimpleNamespace

import pytest

nx = pytest.importorskip("networkx")
pytest.importorskip("osmnx")
pytest.importorskip("geopy")

from common import geocode, isochrone  # noqa: E402
from overpass_fixtures import ORIGIN_LAT, ORIGIN_LON, at  # noqa: E402


def _grid(n=21, spacing_m=80):
    """n x n street grid centred on the fixture origin, with one-way and
    parallel edges mixed in, shaped like an osmnx MultiDiGraph."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    node = lambda i, j: i * n + j  # noqa: E731  (osmnx needs scalar node ids)
    for i in range(n):
        for j in range(n):
            lat, lon = at((i - n // 2) * spacing_m, (j - n // 2) * spacing_m)
            G.add_node(node(i, j), x=lon, y=lat)
    for i in range(n):
        for j in range(n):
            for di, dj in ((1, 0), (0, 1)):
                if i + di < n and j + dj < n:
                    length = spacing_m * (1 + 0.1 * ((i * 7 + j * 3) % 5))
                    G.add_edge(node(i, j), node(i + di, j + dj), length=length)
                    if (i + j) % 4:  # every 4th edge is one-way
                        G.add_edge(node(i + di, j + dj), node(i, j), length=length)
    G.add_edge(node(10, 10), node(10, 11), length=10.0)  # shorter parallel edge
    return G


def _old_compute_isochrone(G, lat, lon, speed_kmh):
    """The pre-refactor algorithm, verbatim apart from the speed argument."""
    import osmnx as ox
    from shapely.geometry import MultiPoint

    for _, _, data in G.edges(data=True):
        data["travel_time"] = data["length"] / (speed_kmh * 1000 / 3600)
    center_node = ox.nearest_nodes(G, lon, lat)
    reachable = nx.single_source_dijkstra_path_length(G, center_node, cutoff=15 * 60, weight="travel_time")
    return MultiPoint([(G.nodes[n]["x"], G.nodes[n]["y"]) for n in reachable]).convex_hull, dict(reachable)


@pytest.mark.parametrize("speed_kmh", [4.5, 15.0])
def test_isochrone_matches_previous_algorithm(speed_kmh):
    G = _grid()
    lat, lon = at(30, -20)
    new = isochrone.compute_isochrone(G.copy(), lat, lon, speed_kmh)
    old_polygon, old_reachable = _old_compute_isochrone(G.copy(), lat, lon, speed_kmh)

    assert new.reachable.keys() == old_reachable.keys()
    for node, secs in old_reachable.items():
        assert new.reachable[node] == pytest.approx(secs)
    assert new.polygon.equals(old_polygon)


def test_isochrone_leaves_shared_graph_untouched():
    G = _grid()
    isochrone.compute_isochrone(G, ORIGIN_LAT, ORIGIN_LON, 4.5)
    assert not any("travel_time" in data for _, _, data in G.edges(data=True))


def test_isochrone_too_few_nodes():
    G = nx.MultiDiGraph(crs="epsg:4326")
    G.add_node(1, x=ORIGIN_LON, y=ORIGIN_LAT)
    with pytest.raises(ValueError, match="Too few reachable nodes"):
        isochrone.compute_isochrone(G, ORIGIN_LAT, ORIGIN_LON, 4.5)


class _FakePhoton:
    calls = []
    result = SimpleNamespace(latitude=43.65, longitude=-79.38)

    def __init__(self, user_agent):
        self.user_agent = user_agent

    def geocode(self, query, timeout):
        _FakePhoton.calls.append((self.user_agent, query))
        if isinstance(_FakePhoton.result, Exception):
            raise _FakePhoton.result
        return _FakePhoton.result


@pytest.fixture
def photon(monkeypatch):
    _FakePhoton.calls = []
    _FakePhoton.result = SimpleNamespace(latitude=43.65, longitude=-79.38)
    monkeypatch.setattr(geocode, "Photon", _FakePhoton)
    return _FakePhoton


def test_geocode_appends_city_bias_and_passes_user_agent(photon):
    assert geocode.geocode_address("100 Queen St W", "agent-x") == (43.65, -79.38)
    geocode.geocode_address("1 Yonge St, toronto, ontario", "agent-x")
    assert photon.calls == [
        ("agent-x", "100 Queen St W, Toronto, Ontario"),
        ("agent-x", "1 Yonge St, toronto, ontario"),
    ]


@pytest.mark.parametrize("result, message", [
    (None, "Address not found"),
    (SimpleNamespace(latitude=45.42, longitude=-75.69), "outside supported Toronto area"),  # Ottawa
])
def test_geocode_errors(photon, result, message):
    photon.result = result
    with pytest.raises(ValueError, match=message):
        geocode.geocode_address("somewhere", "agent-x")


def test_geocode_service_errors_become_value_errors(photon):
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut

    for exc, message in ((GeocoderTimedOut(), "timed out"), (GeocoderServiceError("503"), "service error")):
        photon.result = exc
        with pytest.raises(ValueError, match=message):
            geocode.geocode_address("100 Queen St W", "agent-x")


@pytest.mark.parametrize("app", ["city", "ev", "area"])
def test_app_wrappers_use_their_own_user_agent(photon, app):
    from conftest import load_app_module

    module = load_app_module(f"{app}-scorecard", "geocode")
    module.geocode_address("100 Queen St W")
    assert photon.calls[-1][0] == f"toronto-{app}-scorecard"


def test_address_key():
    assert geocode.address_key("  100 Queen St W, Toronto ") == geocode.address_key("100 queen st w toronto")
    assert geocode.address_key("100 Queen St W") != geocode.address_key("100 Queen St E")
