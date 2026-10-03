"""Widget-level tests for app.py state handling, run with Streamlit's AppTest.
The network-backed pipeline (geocoding, graphs, Overpass) and the map are
replaced with fakes; everything else is the real page code.

Each script loads its app the way common/app_loader.py does — purging the
app dir's bare module names first — since every app has its own app.py,
pipeline.py, mapview.py etc.
"""
import re

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from conftest import REPO_ROOT  # noqa: E402


def _city_script(repo_root: str):
    import sys
    from pathlib import Path

    app_dir = Path(repo_root) / "city-scorecard"
    for name in [p.stem for p in app_dir.glob("*.py")]:
        sys.modules.pop(name, None)
    sys.path.insert(0, repo_root)
    sys.path.insert(0, str(app_dir))

    import app
    from pipeline import ScorecardResult
    from scoring import CategoryScore, apply_weights

    combined = {"grocery": 100, "healthcare": 0, "parks": 50, "schools": 50, "transit": 100, "fitness": 0}

    def fake_run_scorecard(address, weights):
        if "bad" in address:
            raise ValueError(f"Address not found: {address!r}")
        breakdown = {
            cat: CategoryScore(proximity=c, variety=c, combined=float(c), count=1, nearest_min=1.0)
            for cat, c in combined.items()
        }
        return ScorecardResult(address, 43.65, -79.38, apply_weights(breakdown, weights), {}, None, None)

    app.run_scorecard = fake_run_scorecard
    app.render_map = lambda *args, **kwargs: None
    app.st_folium = lambda *args, **kwargs: None
    app.render()


def _ev_script(repo_root: str):
    import sys
    from pathlib import Path

    import geopandas as gpd
    import streamlit as st

    app_dir = Path(repo_root) / "ev-scorecard"
    for name in [p.stem for p in app_dir.glob("*.py")]:
        sys.modules.pop(name, None)
    sys.path.insert(0, repo_root)
    sys.path.insert(0, str(app_dir))

    import app
    from charger_access import ChargerAccessResult
    from home_charging import HomeChargingResult
    from pipeline import ScorecardResult

    def fake_run_scorecard(address):
        st.session_state["pipeline_runs"] = st.session_state.get("pipeline_runs", 0) + 1
        return ScorecardResult(
            address=address, lat=43.65, lon=-79.38,
            home_charging=HomeChargingResult(False, "low", "yes", "n/a"),
            charger_access=None, isochrone_polygon=None,
            nearby_chargers=gpd.GeoDataFrame({"access_code": [], "connector_types": []}, geometry=[]),
            walk_graph=None, reachable={},
        )

    app.run_scorecard = fake_run_scorecard
    app.score_charger_access = lambda *args: ChargerAccessResult(0, 0, 0, 0, None, "F")
    app.render_charger_access_map = lambda *args, **kwargs: None
    app.st_folium = lambda *args, **kwargs: None
    app.render()


def _run(script):
    at = AppTest.from_function(script, args=(str(REPO_ROOT),), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _slider(at, label):
    return next(s for s in at.slider if s.label == label)


def _displayed_scores(at) -> list[int]:
    """Overall scores from the big score cards (the 64px number)."""
    return [
        int(m) for md in at.markdown
        for m in re.findall(r"font-size: 64px[^>]*>(\d+)<", md.value)
    ]


def test_preset_change_moves_sliders():
    at = _run(_city_script)
    assert _slider(at, "Healthcare").value == pytest.approx(0.20)

    at.selectbox(key="profile").select("Senior").run()
    assert _slider(at, "Healthcare").value == pytest.approx(0.30)
    assert _slider(at, "Schools").value == pytest.approx(0.05)


def test_reset_restores_preset_after_manual_change():
    at = _run(_city_script)
    at.selectbox(key="profile").select("Family").run()
    _slider(at, "Transit").set_value(0.9).run()
    assert _slider(at, "Transit").value == pytest.approx(0.9)

    _button(at, "Reset weights to preset").click().run()
    assert _slider(at, "Transit").value == pytest.approx(0.10)


def test_displayed_score_follows_sliders_without_rescoring():
    at = _run(_city_script)
    at.text_input[0].input("100 Queen St W")
    _button(at, "Score It").click().run()
    # General: .2*100 + .2*0 + .15*50 + .15*50 + .2*100 + .1*0 = 55
    assert _displayed_scores(at) == [55]

    for label in ("Healthcare", "Parks", "Schools", "Fitness"):
        _slider(at, label).set_value(0.0)
    at.run()
    # Only grocery + transit weighted, both 100.
    assert _displayed_scores(at) == [100]


def test_compare_shows_errors_when_both_fail_and_clears_them_on_success():
    at = _run(_city_script)
    at.text_input(key="address_a").input("bad one")
    at.text_input(key="address_b").input("bad two")
    _button(at, "Compare").click().run()
    assert [e.value for e in at.error] == ["Address not found: 'bad one'", "Address not found: 'bad two'"]

    at.text_input(key="address_a").input("100 Queen St W")
    at.text_input(key="address_b").input("1 Yonge St")
    _button(at, "Compare").click().run()
    assert len(at.error) == 0
    assert "compare_a_error" not in at.session_state
    assert "compare_b_error" not in at.session_state
    assert len(_displayed_scores(at)) == 2


def test_ev_recheck_ignores_case_spacing_and_commas():
    at = _run(_ev_script)
    def check():
        _button(at, "Check It").click().run()

    at.text_input[0].input("100 Queen St W, Toronto")
    check()
    at.text_input[0].input("  100 queen st w toronto ")
    check()
    assert at.session_state["pipeline_runs"] == 1

    at.text_input[0].input("1 Yonge St")
    check()
    assert at.session_state["pipeline_runs"] == 2
