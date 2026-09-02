import html

import folium
from shapely.geometry import Polygon

from charger_access import GRADE_COLORS, parse_connector_types


def _polygon_to_latlon(polygon: Polygon) -> list[tuple[float, float]]:
    return [(lat, lon) for lon, lat in polygon.exterior.coords]


def _charger_popup_html(row) -> str:
    """Full click-through detail for a charger marker — network, connector
    types, pricing, and access hours, none of which fit in the hover
    tooltip. Values come from NREL free-text fields (see build_ev_data.py)
    and are html-escaped since they're not guaranteed to be clean."""
    address = html.escape(str(row.get("address") or "Charging station"))
    network = html.escape(str(row.get("network") or "Unknown network"))
    access_code = html.escape(str(row.get("access_code", "unknown")))
    connectors = html.escape(str(row.get("connector_types") or "Not listed"))
    pricing = html.escape(str(row.get("pricing") or "Not listed"))
    hours = html.escape(str(row.get("access_hours") or "Not listed"))
    level2 = int(row.get("level2_ports", 0) or 0)
    level3 = int(row.get("level3_ports", 0) or 0)

    return f"""
    <div style="font-family: sans-serif; font-size: 13px; min-width: 200px;">
      <div style="font-weight: 700; margin-bottom: 4px;">{address}</div>
      <div style="color: #555; margin-bottom: 6px;">{network} &middot; {access_code}</div>
      <table style="border-collapse: collapse;">
        <tr><td style="color: #777; padding-right: 8px;">Connectors</td><td>{connectors}</td></tr>
        <tr><td style="color: #777; padding-right: 8px;">Level 2 / DC fast</td><td>{level2} / {level3} ports</td></tr>
        <tr><td style="color: #777; padding-right: 8px;">Pricing</td><td>{pricing}</td></tr>
        <tr><td style="color: #777; padding-right: 8px;">Hours</td><td>{hours}</td></tr>
      </table>
    </div>
    """


def render_charger_access_map(
    lat, lon, address, isochrone_polygon, chargers_gdf, access_result, selected_connectors: set[str]
) -> folium.Map:
    """Isochrone + charger markers + grade badge — the map for every address,
    since public charging access is always scored (see pipeline.py).

    Marker color: private stations are always orange. Public stations are
    green when they're compatible with `selected_connectors`, and greyed
    out ("lightgray") otherwise — including when selected_connectors is
    empty (nothing picked yet), so the map stays visually consistent with
    the connector-gated score in app.py."""
    m = folium.Map(location=(lat, lon), zoom_start=15, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)

    folium.Polygon(
        locations=_polygon_to_latlon(isochrone_polygon),
        color="#43a047", weight=2,
        fill=True, fill_color="#a5d6a7", fill_opacity=0.25,
        tooltip="15-min walk range",
    ).add_to(m)

    folium.Marker(
        location=(lat, lon),
        tooltip=address,
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(m)

    for _, row in chargers_gdf.iterrows():
        ports = int(row.get("total_ports", 0))
        label = row.get("address") or "Charging station"
        is_public = row.get("access_code", "public") == "public"
        is_compatible = bool(parse_connector_types(row.get("connector_types")) & selected_connectors)

        tooltip = f"{label} — {ports} port{'s' if ports != 1 else ''}"
        if not is_public:
            tooltip += f" (access: {row.get('access_code', 'unknown')})"
            color = "orange"
        elif is_compatible:
            color = "green"
        else:
            color = "lightgray"
            tooltip += " (not compatible with your selected connector)"

        folium.Marker(
            location=(row.geometry.y, row.geometry.x),
            tooltip=tooltip,
            popup=folium.Popup(_charger_popup_html(row), max_width=280),
            icon=folium.Icon(color=color, icon="bolt", prefix="fa"),
        ).add_to(m)

    _add_grade_badge(m, access_result)
    return m


def _add_grade_badge(m: folium.Map, result) -> None:
    color = GRADE_COLORS.get(result.grade, "#757575")
    badge_html = f"""
    <div style="
        position: fixed; top: 12px; right: 12px; z-index: 9999;
        background: white; border-radius: 10px; padding: 10px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif;
        text-align: center; min-width: 90px;">
      <div style="font-size: 28px; font-weight: 700; color: {color};">{result.combined:.0f}</div>
      <div style="font-size: 13px; color: #555;">Charging Access</div>
      <div style="
          margin-top: 4px; display: inline-block; background: {color}; color: white;
          border-radius: 6px; padding: 2px 10px; font-weight: 600; font-size: 14px;">
        {result.grade}
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(badge_html))


if __name__ == "__main__":
    from charger_access import query_chargers_in_polygon, score_charger_access
    from data import get_charging_stations
    from geocode import geocode_address
    from isochrone import compute_isochrone
    from network import load_network

    for address in ("100 Queen St W", "35 Playter Blvd"):
        lat, lon = geocode_address(address)
        chargers_gdf = get_charging_stations()
        G = load_network(lat, lon)
        iso = compute_isochrone(G, lat, lon)
        nearby = query_chargers_in_polygon(chargers_gdf, iso.polygon)
        public_nearby = nearby[nearby["access_code"] == "public"]
        result = score_charger_access(public_nearby, G, iso.reachable)
        fmap = render_charger_access_map(lat, lon, address, iso.polygon, nearby, result, {"J1772"})

        out_path = "map_preview_access.html"
        fmap.save(out_path)
        print(f"{address}: saved {out_path}")
