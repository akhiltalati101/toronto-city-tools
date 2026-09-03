import streamlit as st
from streamlit_folium import st_folium

from charger_access import CONNECTOR_LABELS, GRADE_COLORS, filter_by_connectors, score_charger_access
from mapview import render_charger_access_map
from pipeline import ScorecardResult, run_scorecard

# Natural Resources Canada guidance on home Level 2 EV charger installation.
# There's no federal home-charger rebate to link to (as of 2026, the federal
# EVAP program covers vehicle purchases, not charger installs) — only some
# provinces/utilities offer install rebates, and those change/expire often
# enough that we point to the stable federal how-to instead of guessing at a
# provincial program that might be gone by the time someone clicks it.
NRCAN_INSTALL_GUIDE_URL = (
    "https://natural-resources.canada.ca/energy-efficiency/transportation-energy-efficiency/"
    "electric-vehicles/electric-vehicle-charging-charger-installation"
)
NRCAN_COSTS_GUIDE_URL = (
    "https://natural-resources.canada.ca/energy-efficiency/transportation-energy-efficiency/"
    "zero-emission-vehicles/electric-vehicle-charging-costs-ev-charging"
)

st.set_page_config(page_title="Should I Own an EV?", page_icon="🔌", layout="wide")


def _check_password() -> bool:
    """Gate the app behind a shared password stored in st.secrets."""
    if st.session_state.get("authed"):
        return True

    st.markdown(
        """
        <style>
        div[data-testid="stForm"] {
            border: 1px solid rgba(49, 51, 63, 0.15);
            border-radius: 16px;
            padding: 32px 28px 24px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.write("")
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        with st.form("login"):
            st.markdown(
                "<div style='text-align:center; font-size:20px; font-weight:800;'>Should I Own an EV?</div>"
                "<div style='text-align:center; font-size:13px; color:#666; margin-bottom:18px;'>"
                "Enter password to continue</div>",
                unsafe_allow_html=True,
            )
            entered = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
            submitted = st.form_submit_button("Continue", type="primary", use_container_width=True)

        if submitted:
            if entered == st.secrets.get("app_password"):
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


def _render_charger_access_card(access_result, connectors_selected: bool) -> None:
    if not connectors_selected:
        st.markdown(
            """
            <div style="text-align:center; padding: 24px; border-radius: 12px; background: #f5f5f5;">
              <div style="font-size: 40px;">🔌❓</div>
              <div style="font-size: 16px; color: #555; margin-top: 8px;">
                Select your car's connector type(s) below to see your compatible charging score.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    color = GRADE_COLORS.get(access_result.grade, "#757575")
    st.markdown(
        f"""
        <div style="text-align:center; padding: 24px; border-radius: 12px; background: #f5f5f5;">
          <div style="font-size: 64px; font-weight: 800; color: {color};">{access_result.combined:.0f}</div>
          <div style="font-size: 16px; color: #555;">compatible public charging access, out of 100</div>
          <div style="display:inline-block; margin-top:8px; padding: 4px 16px; border-radius: 8px;
                      background: {color}; color: white; font-weight: 700; font-size: 20px;">
            {access_result.grade}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nearest = f"{access_result.nearest_min} min" if access_result.nearest_min is not None else "—"
    count = access_result.count
    st.metric(
        "Compatible Charging Availability",
        f"{count} station{'s' if count != 1 else ''} available",
        help=(
            f"Within a 15-minute walk of this address, with the nearest compatible station "
            f"{nearest} away. Only counts public stations whose connector matches what you "
            "selected below — this score doesn't change based on whether this address can "
            "also charge at home."
        ),
    )


def _render_home_charging_panel(result) -> None:
    """Supplementary panel shown alongside the public-access score whenever
    home Level 2 charging looks feasible at this address. Links to NRCan's
    installation guidance rather than a rebate — there's no federal home-
    charger rebate program (see NRCAN_INSTALL_GUIDE_URL comment above)."""
    st.markdown(
        """
        <div style="padding: 16px 20px; border-radius: 12px; background: #e8f5e9; margin-top: 16px;">
          <div style="font-size: 15px; font-weight: 700; color: #2e7d32;">🏡🔌 Home charging may also be available</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.metric(
        "Residence Type",
        result.dwelling_type,
        help=(
            f"Confidence: {result.confidence}. {result.note} Level 2 (240V) home charging is "
            "typically installable in a private driveway or garage — adds roughly 30–40 km of "
            "range per hour, enough for a full overnight charge. A licensed electrician can "
            "confirm your panel capacity and provide an installation quote."
        ),
    )
    st.caption(
        f"Guidance from Natural Resources Canada: "
        f"[how home charger installation works]({NRCAN_INSTALL_GUIDE_URL}) &middot; "
        f"[what it costs to charge at home]({NRCAN_COSTS_GUIDE_URL}). "
        "Some provinces and utilities offer their own install rebates — check locally, "
        "since there's no federal rebate for home charger installation."
    )


if not _check_password():
    st.stop()

st.title("Should I Own an EV?")
st.caption("See how well a Toronto address is served by public EV charging you can actually plug into — plus whether it can likely support a home charger too.")

with st.expander("How this is calculated"):
    st.markdown(
        """
        The headline score reflects **compatible public charging access**: how many publicly
        available charging stations *your car can actually plug into* are within a 15-minute
        walk, and how close the nearest one is. Select your car's connector type(s) below,
        then hit **Check It** — some networks (e.g. most Tesla Destination/Supercharger
        stations) only work with one connector, so a score that counted every public charger
        regardless of connector would overstate what you can actually use.

        This doesn't change based on whether you personally have a driveway — it's a property
        of the location, useful for road trips, top-ups, or visitors even if you can charge at
        home.

        If the address's building is detected to be a detached, semi-detached, or townhouse
        type that usually has a driveway or garage, a separate panel below the score notes
        that home Level 2 charging may also be available, with installation guidance.
        """
    )

address = st.text_input("Address", placeholder="e.g. 100 Queen St W")

st.subheader("What does your car use?")
st.caption(
    "Select every connector your car supports. Chargers you can't use show up "
    "greyed out on the map and don't count toward your score."
)
connector_cols = st.columns(len(CONNECTOR_LABELS))
current_selection = {
    code
    for col, (code, label) in zip(connector_cols, CONNECTOR_LABELS.items())
    if col.checkbox(label, key=f"connector_{code}")
}

check_clicked = st.button("Check It", type="primary")

# Recalculation only happens on a "Check It" click, not on every checkbox
# toggle — the score below is driven by session_state.selected_connectors,
# a snapshot taken at click time, not by current_selection directly. The
# full pipeline (geocode, Overpass, isochrone) only re-runs when the address
# text actually changed; a connector-only re-check just re-scores the
# already-fetched chargers using the cached walk_graph/reachable.
if check_clicked:
    if not address.strip():
        st.warning("Enter an address first.")
    else:
        try:
            with st.spinner("Checking address..."):
                if st.session_state.get("scorecard_address") != address:
                    st.session_state.scorecard = run_scorecard(address)
                    st.session_state.scorecard_address = address
            st.session_state.selected_connectors = current_selection
        except ValueError as e:
            st.error(str(e))
            st.session_state.pop("scorecard", None)
            st.session_state.pop("scorecard_address", None)

if "scorecard" in st.session_state and "selected_connectors" in st.session_state:
    card: ScorecardResult = st.session_state.scorecard
    selected_connectors = st.session_state.selected_connectors

    public_chargers = card.nearby_chargers[card.nearby_chargers["access_code"] == "public"]
    compatible_chargers = filter_by_connectors(public_chargers, selected_connectors)
    access_result = score_charger_access(compatible_chargers, card.walk_graph, card.reachable)

    col_score, col_map = st.columns([1, 2])
    with col_score:
        _render_charger_access_card(access_result, connectors_selected=bool(selected_connectors))
        if card.home_charging.feasible:
            _render_home_charging_panel(card.home_charging)
    with col_map:
        st.subheader("Map")
        fmap = render_charger_access_map(
            card.lat, card.lon, card.address, card.isochrone_polygon, card.nearby_chargers,
            access_result, selected_connectors,
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
