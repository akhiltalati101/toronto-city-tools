import streamlit as st
from streamlit_folium import st_folium

from amenities import query_amenities
from geocode import geocode_address
from isochrone import compute_isochrone
from mapview import GRADE_COLORS, render_map
from network import load_network
from scoring import PROFILES, score_amenities

CATEGORY_LABELS = {
    "grocery": "Grocery", "healthcare": "Healthcare", "parks": "Parks",
    "schools": "Schools", "transit": "Transit", "fitness": "Fitness",
}

st.set_page_config(page_title="City Scorecard", page_icon="🏙️", layout="wide")

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

address = st.text_input("Address", placeholder="e.g. 100 Queen St W")
score_clicked = st.button("Score It", type="primary")

if score_clicked:
    if not address.strip():
        st.warning("Enter an address first.")
    else:
        try:
            with st.spinner("Geocoding address..."):
                lat, lon = geocode_address(address)

            with st.spinner("Downloading street network..."):
                G_walk = load_network(lat, lon, "walk")
                G_bike = load_network(lat, lon, "bike")

            with st.spinner("Computing 15-minute isochrones..."):
                walk_iso = compute_isochrone(G_walk, lat, lon, "walk")
                bike_iso = compute_isochrone(G_bike, lat, lon, "bike")

            with st.spinner("Finding nearby amenities..."):
                amenities = query_amenities(walk_iso.polygon)

            result = score_amenities(amenities, G_walk, walk_iso.reachable, normalized_weights)

            st.session_state.result = result
            st.session_state.amenities = amenities
            st.session_state.walk_polygon = walk_iso.polygon
            st.session_state.bike_polygon = bike_iso.polygon
            st.session_state.lat = lat
            st.session_state.lon = lon
            st.session_state.scored_address = address
        except ValueError as e:
            st.error(str(e))

if "result" in st.session_state:
    result = st.session_state.result
    amenities = st.session_state.amenities

    col_score, col_chart = st.columns([1, 2])

    with col_score:
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
        st.session_state.lat,
        st.session_state.lon,
        st.session_state.scored_address,
        st.session_state.walk_polygon,
        st.session_state.bike_polygon,
        amenities,
        result,
    )
    st_folium(fmap, width=None, height=550, returned_objects=[])

    with st.expander("Category details"):
        for cat, s in result.breakdown.items():
            nearest = f"{s.nearest_min} min" if s.nearest_min is not None else "—"
            st.write(
                f"**{CATEGORY_LABELS[cat]}** — Score: {s.combined} "
                f"(proximity {s.proximity}, variety {s.variety}) · Count: {s.count} · Nearest: {nearest}"
            )
