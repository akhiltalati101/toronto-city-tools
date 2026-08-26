# Toronto City Tools

Tools to help citizens of Toronto stay more informed and participate in city-related decisions.

**GitHub:** https://github.com/akhiltalati101/toronto-city-tools

---

## City Scorecard

Score any address in Toronto on how well it meets the **15-minute city** standard — groceries, healthcare, parks, schools, transit, and fitness all within a short trip. Using OpenStreetMap data and real street networks, the app surfaces what's nearby, what's missing, and how your neighbourhood compares, with an interactive map you can explore at a glance.

Most planning support tools never reach everyday residents — they're built for specialists, buried in complex interfaces, and hard to connect to real decisions. City Scorecard is the opposite: a clean, consumer-friendly way to understand your neighbourhood's access to daily essentials.

**How it works:** Enter an address and get a score based on amenities reachable within a 15-minute walk or bike ride. Each category (grocery, healthcare, parks, schools, transit, fitness) is scored on proximity (60%, distance to the nearest amenity along real streets) and variety (40%, how many options are within reach). Scores are personalized by profile (General, Family, Senior, Car-Free, Student), with sliders to fine-tune weights.

Built with Python, OSMnx, Folium, and Streamlit, using live OpenStreetMap data via the Overpass API.

**GitHub:** https://github.com/akhiltalati101/toronto-city-tools/tree/main/city-scorecard

---

## Should I Own an EV? (EV Scorecard)

Check any Toronto address for whether it's realistic to own an EV there. First question: can you charge at home? If the address looks like a detached or semi-detached house, home charging is almost always feasible — cheap, convenient, available most nights. If not (apartments, condos, anything without a private driveway or garage), the app instead scores public charging access: how many charging stations are reachable within a 15-minute walk, and how close the nearest one is.

**How it works:**
1. **Home charging check** — looks up the OpenStreetMap building at the address and classifies it by type. Houses are flagged as likely feasible for home charging; apartments/condos fall back to the public charging check.
2. **Public charging access** (fallback only) — reuses City Scorecard's proximity/variety scoring formula, applied to public EV chargers instead of amenities.

Charging station data comes from the City of Toronto's Open Data portal (city-operated/Green P stations, refreshed quarterly); building type comes from OpenStreetMap. It reuses City Scorecard's prebuilt citywide walk network graph rather than rebuilding one.

Built with Python, OSMnx, Folium, and Streamlit.

**GitHub:** https://github.com/akhiltalati101/toronto-city-tools/tree/main/ev-scorecard
