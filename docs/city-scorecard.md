# City Scorecard

Score any address in Toronto on how well it meets the **15-minute city** standard — groceries, healthcare, parks, schools, transit, and fitness all within a short trip. Using OpenStreetMap data and real street networks, the app surfaces what's nearby, what's missing, and how your neighbourhood compares, with an interactive map you can explore at a glance.

Most planning support tools never reach everyday residents: they're built for specialists, buried in complex interfaces, and hard to connect to real decisions. City Scorecard is the opposite — a clean, consumer-friendly way to understand your neighbourhood's access to daily essentials.

## How it works

Enter an address → get a score based on amenities reachable within a 15-minute walk or bike ride.

Each category is scored on two dimensions:
- **Proximity** (60%) — how far is the nearest amenity of this type, measured along real streets
- **Variety** (40%) — how many options are available within the isochrone

Scores are personalised by profile (General, Family, Senior, Car-Free, Student), with sliders to fine-tune weights — the score updates instantly as you drag.

Amenities and the walk/bike street networks come from a citywide OpenStreetMap extract, prebuilt monthly by `scripts/build_city_data.py` (`.github/workflows/rebuild-city-data.yml`) rather than queried live.

## Amenity categories

| Category | What counts |
|---|---|
| Grocery | Supermarkets, convenience stores, greengrocers |
| Healthcare | Hospitals, clinics, pharmacies, doctors |
| Parks | Parks, gardens, playgrounds |
| Schools | Schools, kindergartens, colleges, universities |
| Transit | Bus stops, subway entrances, train stations |
| Fitness | Gyms, swimming pools, sports centres |

## Code & running locally

The scoring logic for this tool lives in `toronto_tools/city/` and is served by the API in `api/`; the UI is the `/city` page of the React app in `frontend/`. See the [README](../README.md) for the architecture and how to run both locally.

## Roadmap

1. **Prototype** *(done)* — Streamlit app: geocode address, compute isochrone, score amenities, render Folium map
2. **Product** *(done)* — FastAPI backend + React + MapLibre frontend
