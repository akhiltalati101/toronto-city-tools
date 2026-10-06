import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Repo root, for `common` — the hub already adds it, but a standalone
# `streamlit run city-scorecard/app.py` needs it before geocode.py imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapview import GRADE_COLORS, render_map  # noqa: E402
from pipeline import ScorecardResult, run_scorecard  # noqa: E402
from scoring import PROFILES, apply_weights  # noqa: E402

CATEGORY_LABELS = {
    "grocery": "Grocery", "healthcare": "Healthcare", "parks": "Parks",
    "schools": "Schools", "transit": "Transit", "fitness": "Fitness",
}

def _render_score_card(result) -> None:
    color = GRADE_COLORS.get(result.grade, "#757575")
    st.markdown(
        f"""
        <div style="text-align:center; padding: 24px; border-radius: 12px; background: #f5f5f5;">
          <div style="font-size: 64px; font-weight: 800; color: {color};">{result.overall:.0f}</div>
          <div style="font-size: 16px; color: #555;">out of 100</div>
          <div style="display:inline-block; margin-top:8px; padding: 4px 16px; border-radius: 8px;
                      background: {color}; color: white; font-weight: 700; font-size: 20px;">
            {result.grade}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_category_details(result) -> None:
    for cat, s in result.breakdown.items():
        nearest = f"{s.nearest_min} min" if s.nearest_min is not None else "—"
        st.write(
            f"**{CATEGORY_LABELS[cat]}** — Score: {s.combined} "
            f"(proximity {s.proximity}, variety {s.variety}) · Count: {s.count} · Nearest: {nearest}"
        )


def _weight_key(cat: str) -> str:
    return f"weight_{cat}"


def _apply_preset() -> None:
    """Load the selected preset into the weight inputs (as whole percents).
    Runs as a widget callback, i.e. before the inputs are drawn, which is the
    only point where their session_state values can be set."""
    for cat, weight in PROFILES[st.session_state.profile].items():
        st.session_state[_weight_key(cat)] = round(weight * 100)
    # Presets sum to 100; set here so the fragment doesn't see it as a change
    # and trigger a second, redundant rerun.
    st.session_state.valid_weights = dict(PROFILES[st.session_state.profile])


def _weights_total() -> int:
    return sum(st.session_state[_weight_key(cat)] for cat in PROFILES["General"])


@st.fragment
def _weight_inputs() -> None:
    """Weight boxes + live total. A fragment, so typing in a box reruns only
    this block: the score and map below aren't redrawn (and don't flicker)
    while the total is off. A full rerun happens only once the total is 100
    and the weights actually differ from the ones in use."""
    st.caption("Enter each category's share in %. Must total 100.")
    percents = {
        cat: st.number_input(
            CATEGORY_LABELS[cat], min_value=0, max_value=100, step=5, key=_weight_key(cat)
        )
        for cat in PROFILES["General"]
    }
    total = sum(percents.values())
    if total != 100:
        diff = 100 - total
        st.error(
            f"Total: {total}% — {'add' if diff > 0 else 'remove'} {abs(diff)}% "
            "to reach 100%. Scoring is paused."
        )
        return

    st.success("Total: 100%")
    new = {k: v / 100 for k, v in percents.items()}
    previous = st.session_state.get("valid_weights")
    st.session_state.valid_weights = new
    if previous is not None and previous != new:
        st.rerun()


def render() -> None:
    st.title("City Scorecard")
    st.caption("Score any Toronto address on the 15-minute city standard.")

    # The inputs are keyed so a preset change can move them: unkeyed, they
    # kept their own values and the preset dropdown silently did nothing
    # until "Reset" was clicked.
    st.session_state.setdefault("profile", "General")
    for cat, weight in PROFILES[st.session_state.profile].items():
        st.session_state.setdefault(_weight_key(cat), round(weight * 100))

    with st.sidebar:
        st.header("Profile")
        st.selectbox("Preset", list(PROFILES.keys()), key="profile", on_change=_apply_preset)
        st.button("Reset weights to preset", on_click=_apply_preset)

        st.header("Fine-tune weights")
        _weight_inputs()
        # Set by the fragment above: the presets sum to 100, so the first run
        # is valid. While the boxes total != 100 this stays the last valid set.
        normalized_weights = st.session_state.valid_weights

    tab_single, tab_compare = st.tabs(["Score an Address", "Compare Addresses"])

    with tab_single:
        address = st.text_input("Address", placeholder="e.g. 100 Queen St W")
        score_clicked = st.button("Score It", type="primary")

        if score_clicked:
            if _weights_total() != 100:
                st.warning("Weights must total 100% before scoring.")
            elif not address.strip():
                st.warning("Enter an address first.")
            else:
                try:
                    with st.spinner("Geocoding address..."):
                        st.session_state.city_scorecard = run_scorecard(address, normalized_weights)
                except ValueError as e:
                    st.error(str(e))
                    st.session_state.pop("city_scorecard", None)

        if "city_scorecard" in st.session_state:
            card: ScorecardResult = st.session_state.city_scorecard
            # Re-weighted on every run, so editing a weight updates the score
            # shown instead of leaving the one computed at click time.
            result = apply_weights(card.result.breakdown, normalized_weights)

            col_score, col_chart = st.columns([1, 2])

            with col_score:
                _render_score_card(result)

            with col_chart:
                st.subheader("Category Breakdown")
                chart_data = {CATEGORY_LABELS[cat]: s.combined for cat, s in result.breakdown.items()}
                st.bar_chart(chart_data)

            missing = [cat for cat, s in result.breakdown.items() if s.combined < 50]
            if missing:
                labels = ", ".join(CATEGORY_LABELS[c] for c in missing)
                st.warning(f"Below-average access: **{labels}**")

            st.subheader("Map")
            fmap = render_map(
                card.lat,
                card.lon,
                card.address,
                card.walk_polygon,
                card.bike_polygon,
                card.amenities,
                result,
            )
            st_folium(fmap, width=None, height=550, returned_objects=[], key="map_single")

            with st.expander("Category details"):
                _render_category_details(result)

    with tab_compare:
        col_a, col_b = st.columns(2)
        with col_a:
            address_a = st.text_input("Address A", placeholder="e.g. 100 Queen St W", key="address_a")
        with col_b:
            address_b = st.text_input("Address B", placeholder="e.g. 25 Rathburn Rd W, Etobicoke", key="address_b")

        compare_clicked = st.button("Compare", type="primary")

        if compare_clicked:
            if _weights_total() != 100:
                st.warning("Weights must total 100% before comparing.")
            elif not address_a.strip() or not address_b.strip():
                st.warning("Enter both addresses first.")
            else:
                # Errors too: a failure from an earlier comparison would
                # otherwise keep showing next to this run's results.
                for key in ("compare_a", "compare_b", "compare_a_error", "compare_b_error"):
                    st.session_state.pop(key, None)
                try:
                    with st.spinner(f"Scoring {address_a}..."):
                        st.session_state.compare_a = run_scorecard(address_a, normalized_weights)
                except ValueError as e:
                    st.session_state.compare_a_error = str(e)
                try:
                    with st.spinner(f"Scoring {address_b}..."):
                        st.session_state.compare_b = run_scorecard(address_b, normalized_weights)
                except ValueError as e:
                    st.session_state.compare_b_error = str(e)

        card_a = st.session_state.get("compare_a")
        card_b = st.session_state.get("compare_b")
        error_a = st.session_state.get("compare_a_error")
        error_b = st.session_state.get("compare_b_error")
        result_a = apply_weights(card_a.result.breakdown, normalized_weights) if card_a else None
        result_b = apply_weights(card_b.result.breakdown, normalized_weights) if card_b else None

        # Errors count too: when both addresses failed, this used to show nothing.
        if card_a or card_b or error_a or error_b:
            if card_a and card_b:
                score_a, score_b = result_a.overall, result_b.overall
                if score_a > score_b:
                    st.success(f"**{card_a.address}** scores higher ({score_a:.0f} vs {score_b:.0f})")
                elif score_b > score_a:
                    st.success(f"**{card_b.address}** scores higher ({score_b:.0f} vs {score_a:.0f})")
                else:
                    st.info(f"Tied at {score_a:.0f}")

            col_a_out, col_b_out = st.columns(2)
            for col, card, result, error in (
                (col_a_out, card_a, result_a, error_a),
                (col_b_out, card_b, result_b, error_b),
            ):
                with col:
                    if card:
                        st.subheader(card.address)
                        _render_score_card(result)
                    elif error:
                        st.error(error)

            if card_a and card_b:
                st.subheader("Category Breakdown")
                chart_data = {
                    CATEGORY_LABELS[cat]: {
                        card_a.address: result_a.breakdown[cat].combined,
                        card_b.address: result_b.breakdown[cat].combined,
                    }
                    for cat in result_a.breakdown
                }
                st.bar_chart(pd.DataFrame(chart_data).T, stack=False)

            col_map_a, col_map_b = st.columns(2)
            for col, card, result, map_key in (
                (col_map_a, card_a, result_a, "map_a"),
                (col_map_b, card_b, result_b, "map_b"),
            ):
                with col:
                    if card:
                        st.subheader("Map")
                        fmap = render_map(
                            card.lat,
                            card.lon,
                            card.address,
                            card.walk_polygon,
                            card.bike_polygon,
                            card.amenities,
                            result,
                        )
                        st_folium(fmap, width=None, height=450, returned_objects=[], key=map_key)

            col_details_a, col_details_b = st.columns(2)
            for col, card, result in ((col_details_a, card_a, result_a), (col_details_b, card_b, result_b)):
                with col:
                    if card:
                        with st.expander(f"Category details — {card.address}"):
                            _render_category_details(result)


if __name__ == "__main__":
    st.set_page_config(page_title="City Scorecard", page_icon=":material/location_city:", layout="wide")
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.auth import check_password
    if check_password("City Scorecard"):
        render()
    else:
        st.stop()
