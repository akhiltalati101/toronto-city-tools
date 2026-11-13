# Toronto City Tools

Tools to help citizens of Toronto stay more informed and participate in city-related decisions.

**GitHub:** https://github.com/akhiltalati101/toronto-city-tools

---

## City Scorecard

Score any Toronto address on the **15-minute city** standard: groceries, healthcare, parks, schools, transit, and fitness within a short trip. Using OpenStreetMap data and real street networks, the app surfaces what's nearby, what's missing, and how your neighbourhood compares, with an interactive map you can explore at a glance.

Most planning support tools never reach everyday residents — they're built for specialists, buried in complex interfaces, and hard to connect to real decisions. City Scorecard is the opposite: a clean, consumer-friendly way to understand your neighbourhood's access to daily essentials.

**How it works:** Enter an address and get a score based on amenities reachable within a 15-minute walk or bike ride. Each category (grocery, healthcare, parks, schools, transit, fitness) is scored on proximity (60%, distance to the nearest amenity along real streets) and variety (40%, how many options are within reach). Scores are personalized by profile (General, Family, Senior, Car-Free, Student), with sliders to fine-tune weights that re-score instantly, side-by-side address comparison, and a map you can click to score any spot.

Built with Python, OSMnx and FastAPI behind a React + MapLibre frontend, using a citywide OpenStreetMap extract rebuilt monthly.

**Details:** https://github.com/akhiltalati101/toronto-city-tools/blob/main/docs/city-scorecard.md

---

## Should I Own an EV? (EV Scorecard)

Can you charge an EV at this Toronto address? Scores how well the address is served by public charging *your car can actually plug into*, and flags when the building looks like it can support a home charger too.

**How it works:**
1. **Compatible public charging access** — pick your car's connector types (J1772, CCS, CHAdeMO, Tesla/NACS) and the score updates instantly: how many compatible public chargers are within a 15-minute walk, and how close the nearest one is, using City Scorecard's proximity/variety formula.
2. **Home charging check** — looks up the OpenStreetMap building at the address and classifies it by type. Detached, semi-detached and townhouse types get a panel noting home Level 2 charging is likely possible, with installation guidance.

Charging station data comes from NREL's Alternative Fuel Stations database (public and private stations across every network, with connector types — refreshed quarterly); building type comes from OpenStreetMap. It reuses City Scorecard's prebuilt citywide walk network graph rather than rebuilding one.

Built with Python, OSMnx, FastAPI, React and MapLibre.

**Details:** https://github.com/akhiltalati101/toronto-city-tools/blob/main/docs/ev-scorecard.md

---

## Should I Live Here? (Area Scorecard)

See what's changing near any Toronto address, how it compares on safety, and the maintenance record if it's a rental apartment.

**How it works:**
1. **Zoning & development** — active City of Toronto planning applications within 400m of the address, queried live against the city's Application Information Centre map layer. Each shows a plain-English summary — generated on first view via OpenRouter (a free model by default) and cached after that, so repeat lookups are instant — or the city's own description if summarization isn't configured, plus a link to the official application page.
2. **Safety** — Toronto Police's Community Safety Indicators (crime) data for the last 6 months within 500m, weighted by severity and compared to the citywide rate for an area that size.
3. **Rental building quality** — if the address looks like an apartment/condo building, its official RentSafeTO evaluation score (elevators, security, cleanliness, etc.) if it's a registered rental building; RentSafeTO doesn't cover owner-occupied condo corporations, so an unmatched building gets an honest note plus a Facebook group search link instead.

LLM summarization cost is capped by a credit limit on the OpenRouter API key itself, not by any app code — the same key is used whether a summary is generated live by the app or pre-warmed citywide by an optional, manually-triggered background job.

Built with Python, FastAPI, React and MapLibre.

**Details:** https://github.com/akhiltalati101/toronto-city-tools/blob/main/docs/area-scorecard.md
