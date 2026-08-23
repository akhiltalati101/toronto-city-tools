# Should I Own an EV?

Check any Toronto address for whether it's realistic to own an EV there. First: **can you charge at home?** If the address looks like a detached or semi-detached house, home charging is almost always the answer — cheap, convenient, available most nights. If not (apartments, condos, anything without a private driveway or garage), the app instead scores **public charging access**: how many charging stations are reachable within a 15-minute walk, and how close the nearest one is.

## How it works

1. **Home charging check** — looks up the OpenStreetMap building at the address and classifies it by type. Detached/semi-detached houses → home charging is likely feasible. Apartments, condos, and other multi-unit buildings → not feasible, so the app checks public charging instead. This is a heuristic based on building *form*, not a direct check for a driveway or garage — see Limitations below.
2. **Public charging access** (fallback only) — uses the same proximity (60%) / variety (40%) scoring formula as [City Scorecard](../city-scorecard)'s walkability score, applied to public EV chargers instead of amenities: how far to the nearest charger, and how many are reachable within a 15-minute walk.

**v1 scope note:** this only checks whether charging is *nearby*. It doesn't check whether that public charging is already saturated by other EV owners in the area (demand), and it doesn't factor in income or neighbourhood equity. Those are planned for a future policy-focused view (see Roadmap).

## Data sources

| Data | Source |
|---|---|
| Charging stations | [City of Toronto Open Data](https://open.toronto.ca/dataset/city-operated-electric-vehicle-charging-station-map/) — city-operated public EV charging stations, refreshed quarterly. Covers city-operated (Green P) stations only, not private-network chargers, so it undercounts total real-world public charging access. |
| Building type (home charging check) | [OpenStreetMap](https://www.openstreetmap.org/), queried live per address via [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) |
| Walk network (15-min isochrone) | Reuses [City Scorecard](../city-scorecard)'s prebuilt citywide walk graph — same street network, no separate build needed here |

## Stack

| Layer | Choice |
|---|---|
| **Core** | Python + [OSMnx](https://osmnx.readthedocs.io/) |
| **Maps** | [Folium](https://python-visualization.github.io/folium/) |
| **UI** | [Streamlit](https://streamlit.io/) |

## Project structure

```
ev-scorecard/
├── geocode.py          # Address → (lat, lon) via Photon
├── home_charging.py    # Home-charging feasibility via OSM building type
├── network.py          # Walk network graph (reuses city-scorecard's release)
├── isochrone.py         # 15-min walk reachability polygon
├── charger_access.py   # Public charging proximity + variety score (fallback only)
├── data.py             # Downloads/caches charger data + the shared walk graph
├── pipeline.py          # geocode -> home-charging-check -> (public fallback), bundled for reuse
├── mapview.py            # Folium map: either a simple marker, or isochrone + chargers + grade badge
├── app.py               # Streamlit UI — the app entry point
├── scripts/
│   └── build_ev_data.py  # Offline build: charging stations + (dormant, for v2) census tract/income data
└── requirements.txt
```

## Getting Started

**Prerequisites:** Python 3.11

### 1. Enter the directory

```bash
cd ev-scorecard
```

### 2. Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set a password

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your own password
```

### 4. Run the app

```bash
streamlit run app.py
```

The first request downloads the prebuilt charging station data (published by `scripts/build_ev_data.py`, see below) and city-scorecard's walk network graph from GitHub Releases, caching both for the life of the process.

## Rebuilding the data

`scripts/build_ev_data.py` fetches charging stations from Toronto Open Data (used by v1), and also fetches + joins Statistics Canada census tract boundaries, population, and income data (built and tested, but **not currently used by the app** — kept dormant for the v2 gap map described below). It's run periodically by `.github/workflows/rebuild-ev-data.yml` (quarterly), which publishes the output as GitHub Release assets under the `ev-data` tag:

```bash
python scripts/build_ev_data.py --out build
```

## Limitations & things to sanity-check

- Home-charging feasibility is a heuristic based on OpenStreetMap's `building` tag — it reflects building *form*, not an actual check for a driveway or garage. Many Toronto buildings are only generically tagged (`building=yes`), which falls back to the public-charging path even for some houses. Townhouses/row houses are treated as feasible but flagged with a caveat, since driveway presence varies by unit.
- The city-operated charging station dataset doesn't include private-network chargers (mall/condo/workplace chargers), so the public charging access score understates real-world options everywhere, not just in specific areas.
- v1 doesn't account for how many other EV owners might already be relying on the same public chargers — a high access grade means chargers are *nearby*, not necessarily that they'll be *available*.

## Roadmap

1. **Should I Own an EV?** *(this app, v1)* — per-address home-charging check, with a public-charging-access score as fallback
2. **Policy gap map (v2)** — a citywide view of areas underserved by public charging, weighted by dwelling density (apartments/places where home charging isn't possible) vs. charger density, from a policy perspective: where does it make sense to add more chargers? Two distinct gap types planned: low-income areas with poor access (equity gap, likely needs government intervention) vs. higher-income areas with poor access (market gap, an opportunity for private charging operators). The census tract/income data pipeline for this already exists in `scripts/build_ev_data.py`, just not wired into the app yet.
3. **Solar panel feasibility** — given an address, rooftop availability, and local weather data, estimate feasible solar capacity and expected yearly output. Not yet scoped.
