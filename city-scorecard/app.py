import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from mapview import GRADE_COLORS, render_map
from pipeline import ScorecardResult, run_scorecard
from scoring import PROFILES

CATEGORY_LABELS = {
    "grocery": "Grocery", "healthcare": "Healthcare", "parks": "Parks",
    "schools": "Schools", "transit": "Transit", "fitness": "Fitness",
}

st.set_page_config(page_title="City Scorecard", page_icon="🏙️", layout="wide")


def _check_password() -> bool:
    """Gate the app behind a shared password stored in st.secrets.

    Cold-start data download + per-request graph/isochrone compute are
    expensive enough that the app shouldn't sit at a fully open public URL.
    """
    if st.session_state.get("authed"):
        return True

    entered = st.text_input("Password", type="password")
    if entered:
        if entered == st.secrets.get("app_password"):
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


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


if not _check_password():
    st.stop()

st.title("🏙️ City Scorecard")
st.caption("Score any Toronto address on the 15-minute city standard.")

if "profile" not in st.session_state:
    st.session_state.profile = "General"
if "weights" not in st.session_state:
    st.session_state.weights = dict(PROFILES["General"])

with st.sidebar:
    st.header("Profile")
    profile = st.selectbox("Preset", list(PROFILES.keys()), key="profile")
    if st.button("Reset weights to preset"):
        st.session_state.weights = dict(PROFILES[profile])
        st.rerun()

    st.header("Fine-tune weights")
    weights = {}
    for cat in PROFILES["General"]:
        default = st.session_state.weights.get(cat, PROFILES[profile][cat])
        weights[cat] = st.slider(CATEGORY_LABELS[cat], 0.0, 1.0, float(default), 0.05)
    total = sum(weights.values())
    normalized_weights = {k: (v / total if total > 0 else 0) for k, v in weights.items()}
    st.caption(f"Weights sum to {total:.2f} — normalized automatically")

tab_single, tab_compare = st.tabs(["Score an Address", "Compare Addresses"])

with tab_single:
    address = st.text_input("Address", placeholder="e.g. 100 Queen St W")
    score_clicked = st.button("Score It", type="primary")

    if score_clicked:
        if not address.strip():
            st.warning("Enter an address first.")
        else:
            try:
                with st.spinner("Geocoding address..."):
                    st.session_state.scorecard = run_scorecard(address, normalized_weights)
            except ValueError as e:
                st.error(str(e))
                st.session_state.pop("scorecard", None)

    if "scorecard" in st.session_state:
        card: ScorecardResult = st.session_state.scorecard
        result = card.result

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
            st.warning(f"⚠️ Below-average access: **{labels}**")

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
        st_folium(fmap, width=None, height=550, returned_objects=[])

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
        if not address_a.strip() or not address_b.strip():
            st.warning("Enter both addresses first.")
        else:
            st.session_state.pop("compare_a", None)
            st.session_state.pop("compare_b", None)
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

    if card_a or card_b:
        if card_a and card_b:
            score_a, score_b = card_a.result.overall, card_b.result.overall
            if score_a > score_b:
                st.success(f"**{card_a.address}** scores higher ({score_a:.0f} vs {score_b:.0f})")
            elif score_b > score_a:
                st.success(f"**{card_b.address}** scores higher ({score_b:.0f} vs {score_a:.0f})")
            else:
                st.info(f"Tied at {score_a:.0f}")

        col_a_out, col_b_out = st.columns(2)
        for col, card, error_key in (
            (col_a_out, card_a, "compare_a_error"),
            (col_b_out, card_b, "compare_b_error"),
        ):
            with col:
                if card:
                    st.subheader(card.address)
                    _render_score_card(card.result)
                elif st.session_state.get(error_key):
                    st.error(st.session_state[error_key])

        if card_a and card_b:
            st.subheader("Category Breakdown")
            chart_data = {
                CATEGORY_LABELS[cat]: {
                    card_a.address: card_a.result.breakdown[cat].combined,
                    card_b.address: card_b.result.breakdown[cat].combined,
                }
                for cat in card_a.result.breakdown
            }
            st.bar_chart(pd.DataFrame(chart_data).T, stack=False)

        col_map_a, col_map_b = st.columns(2)
        for col, card, map_key in (
            (col_map_a, card_a, "map_a"),
            (col_map_b, card_b, "map_b"),
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
                        card.result,
                    )
                    st_folium(fmap, width=None, height=450, returned_objects=[], key=map_key)

        col_details_a, col_details_b = st.columns(2)
        for col, card in ((col_details_a, card_a), (col_details_b, card_b)):
            with col:
                if card:
                    with st.expander(f"Category details — {card.address}"):
                        _render_category_details(card.result)
