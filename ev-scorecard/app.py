import streamlit as st
from streamlit_folium import st_folium

from charger_access import GRADE_COLORS
from mapview import render_charger_access_map, render_home_charging_map
from pipeline import ScorecardResult, run_scorecard

st.set_page_config(page_title="Should I Own an EV?", page_icon="🔌", layout="wide")


def _check_password() -> bool:
    """Gate the app behind a shared password stored in st.secrets."""
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


def _render_home_charging_card(result) -> None:
    st.markdown(
        """
        <div style="text-align:center; padding: 24px; border-radius: 12px; background: #e8f5e9;">
          <div style="font-size: 40px;">🏡🔌</div>
          <div style="font-size: 22px; font-weight: 700; color: #2e7d32;">Home charging likely available</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Building type: {result.dwelling_type} · confidence: {result.confidence}")
    st.info(result.note)
    st.subheader("What this means")
    st.markdown(
        """
        - **Level 2 (240V) home charging** is typically installable in a private driveway or garage —
          adds roughly 30–40 km of range per hour, enough for a full overnight charge.
        - You may need an electrical panel assessment; a licensed electrician can confirm your home's
          capacity and provide an installation quote.
        - Home charging is generally the cheapest and most convenient way to charge an EV day-to-day.
        """
    )


def _render_charger_access_card(home_result, access_result) -> None:
    color = GRADE_COLORS.get(access_result.grade, "#757575")
    st.markdown(
        f"""
        <div style="text-align:center; padding: 24px; border-radius: 12px; background: #f5f5f5;">
          <div style="font-size: 64px; font-weight: 800; color: {color};">{access_result.combined:.0f}</div>
          <div style="font-size: 16px; color: #555;">public charging access, out of 100</div>
          <div style="display:inline-block; margin-top:8px; padding: 4px 16px; border-radius: 8px;
                      background: {color}; color: white; font-weight: 700; font-size: 20px;">
            {access_result.grade}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Home charging not assumed here — {home_result.note}")
    nearest = f"{access_result.nearest_min} min" if access_result.nearest_min is not None else "—"
    st.write(
        f"**{access_result.count}** charging station{'s' if access_result.count != 1 else ''} within a 15-minute walk "
        f"· nearest is **{nearest}** away"
    )
    st.caption(
        "This score reflects nearby public charging supply only — it doesn't yet account for how many "
        "other EV owners nearby might already be using those chargers."
    )


if not _check_password():
    st.stop()

st.title("🔌 Should I Own an EV?")
st.caption("Check whether a Toronto address can support home charging — or how well it's served by public charging nearby.")

with st.expander("How this is calculated"):
    st.markdown(
        """
        First, the app checks whether the address's building (via OpenStreetMap) is a type that
        typically has a private driveway or garage — detached and semi-detached houses, mostly.
        If so, home charging is the answer: cheap, convenient, and available most nights.

        If the building looks like it's multi-unit (apartments, condos, etc.) or its type can't be
        determined, the app instead scores **public charging access**: how many City of Toronto
        charging stations are reachable within a 15-minute walk, and how close the nearest one is —
        using the same proximity/variety formula as [City Scorecard](../city-scorecard)'s walkability score.

        **v1 scope note:** this only checks whether charging is *nearby*, not whether it's already
        saturated by other EV owners in the area, and it doesn't yet factor in income or neighbourhood
        equity. Those are planned for a future policy-focused "gap map" view.
        """
    )

address = st.text_input("Address", placeholder="e.g. 100 Queen St W")
check_clicked = st.button("Check It", type="primary")

if check_clicked:
    if not address.strip():
        st.warning("Enter an address first.")
    else:
        try:
            with st.spinner("Checking address..."):
                st.session_state.scorecard = run_scorecard(address)
        except ValueError as e:
            st.error(str(e))
            st.session_state.pop("scorecard", None)

if "scorecard" in st.session_state:
    card: ScorecardResult = st.session_state.scorecard

    col_score, col_map = st.columns([1, 2])

    if card.home_charging.feasible:
        with col_score:
            _render_home_charging_card(card.home_charging)
        with col_map:
            st.subheader("Map")
            fmap = render_home_charging_map(card.lat, card.lon, card.address)
            st_folium(fmap, width=None, height=450, returned_objects=[])
    else:
        with col_score:
            _render_charger_access_card(card.home_charging, card.charger_access)
        with col_map:
            st.subheader("Map")
            fmap = render_charger_access_map(
                card.lat, card.lon, card.address, card.isochrone_polygon, card.nearby_chargers, card.charger_access,
            )
            st_folium(fmap, width=None, height=450, returned_objects=[])


# --- Compare Addresses -------------------------------------------------
# Removed for v1's "should I own an EV" framing (a single-address yes/no
# tool doesn't need side-by-side comparison the way city-scorecard's
# walkability score does). Left here, commented out, in case a v2 use case
# brings it back — see city-scorecard/app.py for the pattern to restore.
#
# tab_single, tab_compare = st.tabs(["Check an Address", "Compare Addresses"])
# with tab_compare:
#     col_a, col_b = st.columns(2)
#     with col_a:
#         address_a = st.text_input("Address A", key="address_a")
#     with col_b:
#         address_b = st.text_input("Address B", key="address_b")
#     ...
