import streamlit as st
from streamlit_folium import st_folium

from mapview import render_scorecard_map
from pipeline import AreaScorecard, run_scorecard
from safety import GRADE_COLORS as SAFETY_GRADE_COLORS

st.set_page_config(page_title="Should I Live Here?", page_icon="🏘️", layout="wide")


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
                "<div style='text-align:center; font-size:20px; font-weight:800;'>Should I Live Here?</div>"
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


def _rentsafe_color(score: int) -> str:
    if score >= 80:
        return "#2e7d32"
    if score >= 50:
        return "#fbc02d"
    return "#e53935"


def _render_safety_card(safety) -> None:
    color = SAFETY_GRADE_COLORS.get(safety.grade, "#757575")
    st.markdown(
        f"""
        <div style="text-align:center; padding: 20px; border-radius: 12px; background: #f5f5f5;">
          <div style="font-size: 20px; font-weight: 800; color: {color};">{safety.grade}</div>
          <div style="font-size: 13px; color: #555;">vs. citywide average, last {safety.window_days} days</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.metric(
        f"Incidents within {safety.radius_m}m",
        safety.local_incident_count,
        help=(
            f"Severity-weighted count {safety.local_weighted_count} vs. an expected "
            f"{safety.expected_weighted_count} for an area this size if it matched the "
            f"citywide rate (ratio {safety.ratio}x). Weighted more heavily toward assaults "
            "with weapons, robbery, and break-ins than minor theft. Incident locations are "
            "offset to the nearest intersection by Toronto Police for privacy, so treat this "
            "as directional, not address-precise."
        ),
    )
    if safety.category_breakdown:
        st.caption("Breakdown by category:")
        for category, count in sorted(safety.category_breakdown.items(), key=lambda kv: -kv[1]):
            st.markdown(f"- **{category}**: {count}")


def _render_rental_card(rental) -> None:
    building = rental.building
    if not building.is_apartment:
        st.info(f"🏠 {building.note}")
        return

    if rental.rentsafe:
        r = rental.rentsafe
        score = r.overall_score
        color = _rentsafe_color(score) if score is not None else "#757575"
        st.markdown(
            f"""
            <div style="text-align:center; padding: 20px; border-radius: 12px; background: #f5f5f5;">
              <div style="font-size: 40px; font-weight: 800; color: {color};">{score if score is not None else '—'}</div>
              <div style="font-size: 13px; color: #555;">RentSafeTO building score, out of 100</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"{r.storeys or '?'} storeys, {r.units or '?'} units — evaluated {r.evaluated_on or 'n/a'} "
            f"({r.property_type or 'unknown type'})"
        )
        if r.lowest_categories:
            st.caption("Lowest-scoring inspection categories (1=worst, 3=best):")
            for category, cat_score in r.lowest_categories:
                st.markdown(f"- **{category}**: {cat_score}/3")
    else:
        st.warning(
            "🏢 This looks like an apartment/condo building, but it's not registered with "
            "RentSafeTO. That program only covers rental apartment buildings — it does **not** "
            "cover owner-occupied condo corporations, so this is likely a condo, not a missing "
            "data point."
        )
        if rental.facebook_search_url:
            st.link_button("Search Facebook groups for this building", rental.facebook_search_url)


def _render_zoning_section(zoning_applications) -> None:
    st.subheader("🏗️ Zoning & Development Applications Nearby")
    if not zoning_applications:
        st.info("No active zoning or development applications found within 400m of this address.")
        return

    for zd in zoning_applications:
        app = zd.application
        icon = "🏗️" if app.is_major else "📄"
        with st.expander(f"{icon} {app.address} — {app.folder_type} ({app.status})"):
            st.write(zd.display_text)
            if app.aic_url:
                st.link_button("View official application", app.aic_url)


if not _check_password():
    st.stop()

st.title("Should I Live Here?")
st.caption("Check a Toronto address for nearby zoning/development changes, a 6-month crime comparison, and (for rental buildings) official maintenance scores.")

with st.expander("How this is calculated"):
    st.markdown(
        """
        - **Zoning & development** — live lookup against the City of Toronto's Application
          Information Centre for active applications within 400m of the address. Descriptions
          are summarized in plain English on first view (cached after that, so repeat lookups
          are instant) — or shown as the city's own raw text if summarization isn't configured
          or unavailable.
        - **Safety** — Toronto Police's Community Safety Indicators (crime) data for the last
          6 months within 500m of the address, weighted by severity (weapons/robbery/break-ins
          count for more than minor theft) and compared to what you'd expect for an area that
          size if it matched the citywide rate. Incident locations are offset to the nearest
          intersection for privacy, so treat this as directional, not address-precise.
        - **Rental building quality** — if the address looks like an apartment/condo building,
          its official RentSafeTO evaluation score (elevators, security, cleanliness, etc.) if
          it's a registered rental. RentSafeTO doesn't cover owner-occupied condo corporations.
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
    card: AreaScorecard = st.session_state.scorecard

    col_left, col_map = st.columns([1, 2])

    with col_left:
        st.markdown("#### Safety")
        _render_safety_card(card.safety)
        st.markdown("#### Rental Building Quality")
        _render_rental_card(card.rental)

    with col_map:
        st.markdown("#### Map")
        fmap = render_scorecard_map(card)
        st_folium(fmap, width=None, height=520, returned_objects=[])

    _render_zoning_section(card.zoning_applications)
