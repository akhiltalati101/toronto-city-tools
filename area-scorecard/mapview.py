import html

import folium

from pipeline import AreaScorecard, ZoningApplicationDisplay
from safety import GRADE_COLORS as SAFETY_GRADE_COLORS
from safety import SafetyResult

# Icon per application type — distinguishes visible neighbourhood-scale
# change (new buildings, road/site work) from routine property-level
# paperwork (a homeowner's setback variance), without hiding the latter.
ZONING_ICON = {
    "major": ("blue", "building"),      # Community planning / TLAB
    "minor": ("lightgray", "file-alt"),  # C of A minor variances, etc.
}


def _zoning_popup_html(zd: ZoningApplicationDisplay) -> str:
    app = zd.application
    address = html.escape(app.address or "Unknown address")
    folder_type = html.escape(app.folder_type)
    status = html.escape(app.status)
    summary = html.escape(zd.display_text)
    link_html = ""
    if app.aic_url:
        url = html.escape(app.aic_url)
        link_html = f'<div style="margin-top:6px;"><a href="{url}" target="_blank" rel="noopener">View official application &rarr;</a></div>'

    return f"""
    <div style="font-family: sans-serif; font-size: 13px; min-width: 220px; max-width: 280px;">
      <div style="font-weight: 700; margin-bottom: 2px;">{address}</div>
      <div style="color: #555; margin-bottom: 6px;">{folder_type} &middot; {status}</div>
      <div>{summary}</div>
      {link_html}
    </div>
    """


def _add_zoning_markers(m: folium.Map, zoning_applications: list[ZoningApplicationDisplay]) -> None:
    for zd in zoning_applications:
        app = zd.application
        color, icon = ZONING_ICON["major" if app.is_major else "minor"]
        folium.Marker(
            location=(app.lat, app.lon),
            tooltip=f"{app.folder_type} — {app.address}",
            popup=folium.Popup(_zoning_popup_html(zd), max_width=300),
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
        ).add_to(m)


def _add_safety_layer(m: folium.Map, lat: float, lon: float, safety: SafetyResult) -> None:
    color = SAFETY_GRADE_COLORS.get(safety.grade, "#757575")
    folium.Circle(
        location=(lat, lon),
        radius=safety.radius_m,
        color=color, weight=2,
        fill=True, fill_color=color, fill_opacity=0.08,
        tooltip=f"{safety.radius_m}m catchment — {safety.local_incident_count} incidents in last {safety.window_days} days",
    ).add_to(m)

    badge_html = f"""
    <div style="
        position: fixed; top: 12px; right: 12px; z-index: 9999;
        background: white; border-radius: 10px; padding: 10px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif;
        text-align: center; min-width: 140px;">
      <div style="font-size: 15px; font-weight: 700; color: {color};">{safety.grade}</div>
      <div style="font-size: 12px; color: #555;">vs. citywide (6 mo)</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(badge_html))


def _home_popup_html(card: AreaScorecard) -> str:
    address = html.escape(card.address)
    rental = card.rental
    rental_html = ""
    if rental.building.is_apartment:
        if rental.rentsafe:
            r = rental.rentsafe
            score = "—" if r.overall_score is None else r.overall_score
            rental_html = f'<div style="margin-top:6px;">RentSafeTO score: <b>{score}</b> (evaluated {html.escape(r.evaluated_on or "n/a")})</div>'
        else:
            rental_html = '<div style="margin-top:6px; color:#777;">Not a registered rental building (may be a condo corp).</div>'

    return f"""
    <div style="font-family: sans-serif; font-size: 13px; min-width: 200px;">
      <div style="font-weight: 700;">{address}</div>
      {rental_html}
    </div>
    """


def render_scorecard_map(card: AreaScorecard) -> folium.Map:
    m = folium.Map(location=(card.lat, card.lon), zoom_start=16, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)

    folium.Marker(
        location=(card.lat, card.lon),
        tooltip=card.address,
        popup=folium.Popup(_home_popup_html(card), max_width=260),
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(m)

    _add_safety_layer(m, card.lat, card.lon, card.safety)
    _add_zoning_markers(m, card.zoning_applications)

    return m


if __name__ == "__main__":
    from pipeline import run_scorecard

    for address in ("100 Queen St W", "35 Playter Blvd"):
        card = run_scorecard(address)
        fmap = render_scorecard_map(card)
        out_path = f"map_preview_{address.split()[0]}.html"
        fmap.save(out_path)
        print(f"{address}: saved {out_path}")
