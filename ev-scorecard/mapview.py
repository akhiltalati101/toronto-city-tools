import folium
from folium import FeatureGroup
from shapely.geometry import Polygon


def _polygon_to_latlon(polygon: Polygon) -> list[tuple[float, float]]:
    return [(lat, lon) for lon, lat in polygon.exterior.coords]


def render_map(lat, lon, address, tract_geometry, chargers_gdf, supply_result) -> folium.Map:
    """Build a Folium map: census tract boundary, charging stations, supply-index badge."""
    m = folium.Map(location=(lat, lon), zoom_start=14, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)

    folium.Polygon(
        locations=_polygon_to_latlon(tract_geometry),
        color=supply_result.color, weight=2,
        fill=True, fill_color=supply_result.color, fill_opacity=0.15,
        tooltip=f"Census tract {supply_result.ct_uid} — {supply_result.label}",
    ).add_to(m)

    folium.Marker(
        location=(lat, lon),
        tooltip=address,
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(m)

    group = FeatureGroup(name=f"Charging stations ({len(chargers_gdf)})", show=True)
    for _, row in chargers_gdf.iterrows():
        ports = int(row.get("total_ports", 0))
        label = row.get("address") or "Charging station"
        folium.Marker(
            location=(row.geometry.y, row.geometry.x),
            tooltip=f"{label} — {ports} port{'s' if ports != 1 else ''}",
            icon=folium.Icon(color="green", icon="bolt", prefix="fa"),
        ).add_to(group)
    group.add_to(m)

    _add_supply_badge(m, supply_result)
    _add_legend(m, supply_result)

    return m


def _add_supply_badge(m: folium.Map, result) -> None:
    html = f"""
    <div style="
        position: fixed; top: 12px; right: 12px; z-index: 9999;
        background: white; border-radius: 10px; padding: 10px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif;
        text-align: center; min-width: 140px;">
      <div style="font-size: 28px; font-weight: 700; color: {result.color};">{result.supply_index}</div>
      <div style="font-size: 13px; color: #555;">Supply Index</div>
      <div style="
          margin-top: 4px; display: inline-block; background: {result.color}; color: white;
          border-radius: 6px; padding: 2px 10px; font-weight: 600; font-size: 13px;">
        {result.label}
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


def _add_legend(m: folium.Map, result) -> None:
    html = f"""
    <div style="
        position: fixed; bottom: 24px; left: 12px; z-index: 9999;
        background: white; border-radius: 8px; padding: 10px 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif; font-size: 13px; color: #212121;">
      <div style="font-weight:700; margin-bottom:4px;">Census Tract {result.ct_uid}</div>
      <div>Income percentile: {result.income_percentile * 100:.0f}th</div>
      <div>Ports in tract: {result.port_count} · Population: {result.population:,}</div>
      <div><i class="fa fa-bolt" style="color:green; width:16px; display:inline-block;"></i> Charging station</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


if __name__ == "__main__":
    from data import get_census_tracts, get_charging_stations
    from geocode import geocode_address
    from supply_demand import compute_supply_index

    address = "100 Queen St W"
    lat, lon = geocode_address(address)

    ct_gdf = get_census_tracts()
    chargers_gdf = get_charging_stations()
    result = compute_supply_index(lat, lon, ct_gdf, chargers_gdf, k=1.0)

    tract_geometry = ct_gdf[ct_gdf["ct_uid"] == result.ct_uid].iloc[0].geometry
    nearby_chargers = chargers_gdf[chargers_gdf["ct_uid"] == result.ct_uid]

    fmap = render_map(lat, lon, address, tract_geometry, nearby_chargers, result)
    out_path = "map_preview.html"
    fmap.save(out_path)
    print(f"Saved {out_path} — supply index {result.supply_index} [{result.label}]")
