import folium
from folium import FeatureGroup, LayerControl
from shapely.geometry import Polygon

CATEGORY_STYLE = {
    "grocery":    {"color": "green",     "icon": "shopping-cart"},
    "healthcare": {"color": "red",       "icon": "plus-square"},
    "parks":      {"color": "darkgreen", "icon": "tree"},
    "schools":    {"color": "blue",      "icon": "graduation-cap"},
    "transit":    {"color": "purple",    "icon": "bus"},
    "fitness":    {"color": "orange",    "icon": "heartbeat"},
}

GRADE_COLORS = {"A": "#2e7d32", "B": "#66bb6a", "C": "#fbc02d", "D": "#fb8c00", "F": "#e53935"}


def _polygon_to_latlon(polygon: Polygon) -> list[tuple[float, float]]:
    return [(lat, lon) for lon, lat in polygon.exterior.coords]


def _amenity_name(row, fallback: str) -> str:
    name = row.get("name")
    if not isinstance(name, str) or not name.strip():
        return fallback
    return name


def render_map(lat, lon, address, walk_polygon, bike_polygon, amenities, score_result) -> folium.Map:
    """Build a Folium map: isochrones, amenity markers, score badge, legend."""
    m = folium.Map(location=(lat, lon), zoom_start=15, tiles="OpenStreetMap")

    folium.Polygon(
        locations=_polygon_to_latlon(bike_polygon),
        color="#1e88e5", weight=2, dash_array="6,6",
        fill=True, fill_color="#90caf9", fill_opacity=0.12,
        tooltip="15-min bike range",
    ).add_to(m)

    folium.Polygon(
        locations=_polygon_to_latlon(walk_polygon),
        color="#43a047", weight=2,
        fill=True, fill_color="#a5d6a7", fill_opacity=0.25,
        tooltip="15-min walk range",
    ).add_to(m)

    folium.Marker(
        location=(lat, lon),
        tooltip=address,
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(m)

    for category, gdf in amenities.items():
        style = CATEGORY_STYLE.get(category, {"color": "gray", "icon": "circle"})
        label = category.capitalize()
        group = FeatureGroup(name=f"{label} ({len(gdf)})", show=True)
        for _, row in gdf.iterrows():
            folium.Marker(
                location=(row.geometry.y, row.geometry.x),
                tooltip=_amenity_name(row, label),
                icon=folium.Icon(color=style["color"], icon=style["icon"], prefix="fa"),
            ).add_to(group)
        group.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    _add_score_badge(m, score_result)
    _add_legend(m)

    return m


def _add_score_badge(m: folium.Map, score_result) -> None:
    color = GRADE_COLORS.get(score_result.grade, "#757575")
    html = f"""
    <div style="
        position: fixed; top: 12px; right: 12px; z-index: 9999;
        background: white; border-radius: 10px; padding: 10px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif;
        text-align: center; min-width: 90px;">
      <div style="font-size: 28px; font-weight: 700; color: {color};">{score_result.overall:.0f}</div>
      <div style="font-size: 13px; color: #555;">Score</div>
      <div style="
          margin-top: 4px; display: inline-block; background: {color}; color: white;
          border-radius: 6px; padding: 2px 10px; font-weight: 600; font-size: 14px;">
        {score_result.grade}
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


def _add_legend(m: folium.Map) -> None:
    rows = "".join(
        f'<div style="margin:2px 0;"><i class="fa fa-{style["icon"]}" '
        f'style="color:{style["color"]}; width:16px; display:inline-block;"></i> {cat.capitalize()}</div>'
        for cat, style in CATEGORY_STYLE.items()
    )
    html = f"""
    <div style="
        position: fixed; bottom: 24px; left: 12px; z-index: 9999;
        background: white; border-radius: 8px; padding: 10px 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif; font-size: 13px;">
      <div style="font-weight:700; margin-bottom:4px;">Legend</div>
      {rows}
      <hr style="margin:6px 0;">
      <div><span style="display:inline-block;width:14px;height:10px;background:#a5d6a7;border:1px solid #43a047;"></span> Walk (15 min)</div>
      <div><span style="display:inline-block;width:14px;height:10px;background:#90caf9;border:1px dashed #1e88e5;"></span> Bike (15 min)</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


if __name__ == "__main__":
    from amenities import query_amenities
    from geocode import geocode_address
    from isochrone import compute_isochrone
    from network import load_network
    from scoring import PROFILES, score_amenities

    address = "100 Queen St W"
    lat, lon = geocode_address(address)

    G_walk = load_network(lat, lon, "walk")
    G_bike = load_network(lat, lon, "bike")

    walk_iso = compute_isochrone(G_walk, lat, lon, "walk")
    bike_iso = compute_isochrone(G_bike, lat, lon, "bike")

    amenities = query_amenities(walk_iso.polygon)
    result = score_amenities(amenities, G_walk, walk_iso.reachable, PROFILES["General"])

    fmap = render_map(lat, lon, address, walk_iso.polygon, bike_iso.polygon, amenities, result)
    out_path = "map_preview.html"
    fmap.save(out_path)
    print(f"Saved {out_path} — overall score {result.overall:.1f} [{result.grade}]")
