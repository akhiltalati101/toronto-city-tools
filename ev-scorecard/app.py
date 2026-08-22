import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from mapview import render_map
from pipeline import ScorecardResult, run_scorecard

st.set_page_config(page_title="EV Charging Scorecard", page_icon="🔌", layout="wide")


def _check_password() -> bool:
    """Gate the app behind a shared password stored in st.secrets.

    Cold-start data download is expensive enough that the app shouldn't sit
    at a fully open public URL.
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
    st.markdown(
        f"""
        <div style="text-align:center; padding: 24px; border-radius: 12px; background: #f5f5f5;">
          <div style="font-size: 64px; font-weight: 800; color: {result.color};">{result.supply_index}</div>
          <div style="font-size: 16px; color: #555;">supply index (1.0 = at benchmark)</div>
          <div style="display:inline-block; margin-top:8px; padding: 4px 16px; border-radius: 8px;
                      background: {result.color}; color: white; font-weight: 700; font-size: 20px;">
            {result.label}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_details(result) -> None:
    nearest = f"{result.nearest_charger_m:.0f} m" if result.nearest_charger_m is not None else "—"
    st.write(f"**Census tract:** {result.ct_uid}")
    st.write(
        f"**Local supply:** {result.local_ratio} ports / 1,000 residents "
        f"(citywide average: {result.citywide_avg_ratio})"
    )
    st.write(f"**Income-adjusted benchmark:** {result.benchmark} ports / 1,000 residents")
    st.write(f"**Income percentile:** {result.income_percentile * 100:.0f}th (of all Toronto tracts)")
    st.write(f"**Population:** {result.population:,} · **Ports in tract:** {result.port_count}")
    st.write(f"**Nearest charger:** {nearest}")


if not _check_password():
    st.stop()

st.title("🔌 EV Charging Scorecard")
st.caption("Is this Toronto address underserved or overserved by public EV charging, relative to local need?")

with st.expander("How this is calculated"):
    st.markdown(
        """
        Each address is located within its Statistics Canada **census tract**. The tract's public
        charging **supply** (ports per 1,000 residents) is compared to a citywide average
        **benchmark**, which is adjusted by the tract's median household **income percentile**:
        lower-income tracts are held to a *higher* expected supply bar, not a lower one — the
        assumption being that scarce public charging is itself a barrier to EV adoption in those
        areas, rather than a sign of lower need. This is a modeling choice, not a neutral fact —
        treat the result as a starting point for discussion, not a verdict.

        **Supply index** = local ratio ÷ income-adjusted benchmark. Below 1.0 means underserved
        relative to the benchmark; above 1.0 means overserved.
        """
    )

if "k" not in st.session_state:
    st.session_state.k = 1.0

with st.sidebar:
    st.header("Equity weighting")
    k = st.slider(
        "How much should income shift the benchmark?", 0.0, 2.0, st.session_state.k, 0.1,
        help="0 = income-blind (plain citywide average ratio). Higher values push the benchmark up for lower-income tracts.",
    )
    st.session_state.k = k

tab_single, tab_compare = st.tabs(["Check an Address", "Compare Addresses"])

with tab_single:
    address = st.text_input("Address", placeholder="e.g. 100 Queen St W")
    check_clicked = st.button("Check It", type="primary")

    if check_clicked:
        if not address.strip():
            st.warning("Enter an address first.")
        else:
            try:
                with st.spinner("Geocoding address..."):
                    st.session_state.scorecard = run_scorecard(address, k)
            except ValueError as e:
                st.error(str(e))
                st.session_state.pop("scorecard", None)

    if "scorecard" in st.session_state:
        card: ScorecardResult = st.session_state.scorecard
        result = card.result

        col_score, col_details = st.columns([1, 2])

        with col_score:
            _render_score_card(result)

        with col_details:
            st.subheader("Details")
            _render_details(result)

        st.subheader("Map")
        fmap = render_map(card.lat, card.lon, card.address, card.tract_geometry, card.nearby_chargers, result)
        st_folium(fmap, width=None, height=550, returned_objects=[])

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
                    st.session_state.compare_a = run_scorecard(address_a, k)
            except ValueError as e:
                st.session_state.compare_a_error = str(e)
            try:
                with st.spinner(f"Scoring {address_b}..."):
                    st.session_state.compare_b = run_scorecard(address_b, k)
            except ValueError as e:
                st.session_state.compare_b_error = str(e)

    card_a = st.session_state.get("compare_a")
    card_b = st.session_state.get("compare_b")

    if card_a or card_b:
        if card_a and card_b:
            idx_a, idx_b = card_a.result.supply_index, card_b.result.supply_index
            if idx_a > idx_b:
                st.success(f"**{card_a.address}** is better served ({idx_a} vs {idx_b})")
            elif idx_b > idx_a:
                st.success(f"**{card_b.address}** is better served ({idx_b} vs {idx_a})")
            else:
                st.info(f"Tied at {idx_a}")

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
            st.subheader("Supply Index Comparison")
            chart_data = pd.DataFrame(
                {"Supply Index": [card_a.result.supply_index, card_b.result.supply_index]},
                index=[card_a.address, card_b.address],
            )
            st.bar_chart(chart_data)

        col_map_a, col_map_b = st.columns(2)
        for col, card, map_key in (
            (col_map_a, card_a, "map_a"),
            (col_map_b, card_b, "map_b"),
        ):
            with col:
                if card:
                    st.subheader("Map")
                    fmap = render_map(
                        card.lat, card.lon, card.address, card.tract_geometry, card.nearby_chargers, card.result,
                    )
                    st_folium(fmap, width=None, height=450, returned_objects=[], key=map_key)

        col_details_a, col_details_b = st.columns(2)
        for col, card in ((col_details_a, card_a), (col_details_b, card_b)):
            with col:
                if card:
                    with st.expander(f"Details — {card.address}"):
                        _render_details(card.result)
