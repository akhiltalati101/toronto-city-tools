import folium
from shapely.geometry import Polygon

from charger_access import GRADE_COLORS


def _polygon_to_latlon(polygon: Polygon) -> list[tuple[float, float]]:
    return [(lat, lon) for lon, lat in polygon.exterior.coords]


def render_home_charging_map(lat: float, lon: float, address: str) -> folium.Map:
    """Simple confirmation map for the home-charging branch — no isochrone
    or public chargers to show, just the address itself."""
    m = folium.Map(location=(lat, lon), zoom_start=17, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)
    folium.Marker(
        location=(lat, lon),
        tooltip=address,
        icon=folium.Icon(color="green", icon="home", prefix="fa"),
    ).add_to(m)
    return m


def render_charger_access_map(lat, lon, address, isochrone_polygon, chargers_gdf, access_result) -> folium.Map:
    """Isochrone + charger markers + grade badge, for the public-charging branch."""
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
        folium.Marker(
            location=(row.geometry.y, row.geometry.x),
            tooltip=f"{label} — {ports} port{'s' if ports != 1 else ''}",
            icon=folium.Icon(color="green", icon="bolt", prefix="fa"),
        ).add_to(m)

    _add_grade_badge(m, access_result)
    return m


def _add_grade_badge(m: folium.Map, result) -> None:
    color = GRADE_COLORS.get(result.grade, "#757575")
    html = f"""
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
    m.get_root().html.add_child(folium.Element(html))


if __name__ == "__main__":
    from charger_access import query_chargers_in_polygon, score_charger_access
    from data import get_charging_stations
    from geocode import geocode_address
    from home_charging import check_home_charging
    from isochrone import compute_isochrone
    from network import load_network

    for address in ("100 Queen St W", "35 Playter Blvd"):
        lat, lon = geocode_address(address)
        home_result = check_home_charging(lat, lon)

        if home_result.feasible:
            fmap = render_home_charging_map(lat, lon, address)
            out_path = "map_preview_home.html"
        else:
            chargers_gdf = get_charging_stations()
            G = load_network(lat, lon)
            iso = compute_isochrone(G, lat, lon)
            nearby = query_chargers_in_polygon(chargers_gdf, iso.polygon)
            result = score_charger_access(nearby, G, iso.reachable)
            fmap = render_charger_access_map(lat, lon, address, iso.polygon, nearby, result)
            out_path = "map_preview_access.html"

        fmap.save(out_path)
        print(f"{address}: saved {out_path} (home_feasible={home_result.feasible})")
