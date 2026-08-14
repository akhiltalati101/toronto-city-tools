# City Scorecard

Score any address in Toronto on how well it meets the **15-minute city** standard — groceries, healthcare, parks, schools, transit, and fitness all within a short trip. Using OpenStreetMap data and real street networks, the app surfaces what's nearby, what's missing, and how your neighbourhood compares, with an interactive map you can explore at a glance.

Most planning support tools never reach everyday residents: they're built for specialists, buried in complex interfaces, and hard to connect to real decisions. City Scorecard is the opposite — a clean, consumer-friendly way to understand your neighbourhood's access to daily essentials.

## How it works

Enter an address → get a score based on amenities reachable within a 15-minute walk or bike ride.

Each category is scored on two dimensions:
- **Proximity** (60%) — how far is the nearest amenity of this type, measured along real streets
- **Variety** (40%) — how many options are available within the isochrone

Scores are personalised by profile (General, Family, Senior, Car-Free, Student), with sliders to fine-tune weights.

## Amenity categories

| Category | What counts |
|---|---|
| Grocery | Supermarkets, convenience stores, greengrocers |
| Healthcare | Hospitals, clinics, pharmacies, doctors |
| Parks | Parks, gardens, playgrounds |
| Schools | Schools, kindergartens, colleges, universities |
| Transit | Bus stops, subway entrances, train stations |
| Fitness | Gyms, swimming pools, sports centres |

## Stack

| Layer | Choice |
|---|---|
| **Core** | Python + [OSMnx](https://osmnx.readthedocs.io/) |
| **Maps** | [Folium](https://python-visualization.github.io/folium/) |
| **UI** | [Streamlit](https://streamlit.io/) |
| **Data** | [OpenStreetMap](https://www.openstreetmap.org/) via [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) |

## Project structure

```
city-scorecard/
├── geocode.py      # Address → (lat, lon) via Nominatim
├── network.py      # Street network download + disk cache (OSMnx)
├── isochrone.py    # 15-min walk/bike reachability polygon + travel times
├── amenities.py    # Overpass API queries by category
├── scoring.py      # Proximity + variety scoring, profiles, grade
├── mapview.py      # Folium map: isochrones, amenity markers, legend, score badge
├── app.py          # Streamlit UI — the app entry point
└── requirements.txt
```

## Getting Started

**Prerequisites:** Python 3.9+

### 1. Enter the directory

```bash
cd city-scorecard
```

### 2. Create the virtual environment

```bash
python3 -m venv .venv --without-pip
source .venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Activate the venv (every new terminal session)

```bash
source .venv/bin/activate
```

You'll see `(.venv)` in your prompt when it's active.

### 5. Run the app

```bash
streamlit run app.py
```

## Roadmap

1. **Prototype** *(done)* — Streamlit app: geocode address, compute isochrone, score amenities, render Folium map
2. **Product** — FastAPI backend + React + Mapbox frontend
