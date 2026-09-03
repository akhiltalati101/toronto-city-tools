# Should I Own an EV?

Check any Toronto address for how well it's served by public EV charging *you can actually plug into* — and whether it can likely support a home charger too. The headline score reflects **compatible public charging access**: how many charging stations that match your car's connector are reachable within a 15-minute walk, and how close the nearest one is. Select your connector type(s) below the map to see it — some networks (most Tesla Destination/Supercharger stations) only work with one connector, so counting every public charger regardless of connector would overstate what you can actually use. This is a property of the location, not of who lives there, so it's shown for every address — useful for road trips, top-ups, or visitors even if you can also charge at home. A separate supplementary panel notes when the address's building looks like it can support a **home Level 2 charger**, with installation guidance.

## How it works

1. **Compatible public charging access** — proximity (60%) / variety (40%) scoring formula, shared with [City Scorecard](../city-scorecard)'s walkability score but applied to public EV chargers instead of amenities: how far to the nearest *compatible* charger, and how many are reachable within a 15-minute walk. Gated on connector selection — the score is 0 until you pick at least one connector type (J1772, CCS/J1772 Combo, CHAdeMO, or Tesla/NACS/J3400) below the map; chargers that don't match are greyed out on the map. Click a charger marker for its network, connector types, pricing, and access hours.
2. **Home charging check** (supplementary) — looks up the OpenStreetMap building at the address and classifies it by type. Detached/semi-detached houses and townhouses are flagged as likely home-charging-feasible, with a panel linking to Natural Resources Canada's installation guidance (there's no federal home-charger rebate to link to — see the app's panel for why). This is a heuristic based on building *form*, not a direct check for a driveway or garage — see Limitations below.

**Scope note:** this only checks whether charging is *nearby*. It doesn't check whether that public charging is already saturated by other EV owners in the area (demand), and it doesn't factor in income or neighbourhood equity. Those are planned for a future policy-focused view (see Roadmap). See `docs/algorithm_audit.md` for a full audit of the scoring assumptions and known limitations.

## Data sources

| Data | Source |
|---|---|
| Charging stations | [NREL Alternative Fuel Stations API](https://developer.nrel.gov/docs/transportation/alt-fuel-stations-v1/) (DOE/AFDC database) — all public *and* private-access EV charging in the GTA, across every network (ChargePoint, FLO, Tesla, etc.), not just city-operated stations. Includes network, connector types, port counts, pricing, and access hours where reported. Refreshed periodically by `scripts/build_ev_data.py`. |
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
├── charger_access.py   # Public charging proximity + variety score (always computed)
├── data.py             # Downloads/caches charger data + the shared walk graph
├── pipeline.py          # geocode -> home-charging-check + public-charging-score, bundled for reuse
├── mapview.py            # Folium map: isochrone + charger markers (with click popups) + grade badge
├── app.py               # Streamlit UI — the app entry point
├── docs/
│   └── algorithm_audit.md # Scoring methodology audit: findings, recalibration, spot-checks
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

`scripts/build_ev_data.py` fetches charging stations from the NREL API (requires an `NREL_API_KEY` env var — a free key from [developer.nrel.gov/signup](https://developer.nrel.gov/signup/)), and also fetches + joins Statistics Canada census tract boundaries, population, and income data (built and tested, but **not currently used by the app** — kept dormant for the v2 gap map described below). It's run periodically by `.github/workflows/rebuild-ev-data.yml` (quarterly), which publishes the output as GitHub Release assets under the `ev-data` tag:

```bash
python scripts/build_ev_data.py --out build
```

## Limitations & things to sanity-check

- Home-charging feasibility is a heuristic based on OpenStreetMap's `building` tag — it reflects building *form*, not an actual check for a driveway or garage. Many Toronto buildings are only generically tagged (`building=yes`), which reads as infeasible even for some actual houses. Townhouses/row houses are treated as feasible but flagged with a caveat, since driveway presence varies by unit.
- The isochrone polygon is a convex hull of walk-network-reachable nodes, not the true reachable shape — it can overstate walkable area near natural or built barriers (ravines, highways, rail corridors). See `docs/algorithm_audit.md`.
- The public-access score doesn't account for how many other EV owners might already be relying on the same chargers — a high grade means chargers are *nearby*, not necessarily that they'll be *available*.
- Charging station pricing is only reported by a minority of networks in NREL's data — most stations show "Not listed" rather than an actual rate.
- The variety-score target (`TARGET_CHARGER_COUNT`, see `docs/algorithm_audit.md`) was calibrated against all public chargers combined. Filtering to a single connector (e.g. CHAdeMO only) will show a lower count and thus a lower variety score than the unfiltered number would — that's correct behavior (fewer usable stations), not a threshold that needs re-tuning per connector.

## Roadmap

1. **Should I Own an EV?** *(this app)* — per-address connector-compatible public-charging-access score, with a home-charging feasibility panel and install guidance alongside it
2. **Policy gap map (v2)** — a citywide view of areas underserved by public charging, weighted by dwelling density (apartments/places where home charging isn't possible) vs. charger density, from a policy perspective: where does it make sense to add more chargers? Two distinct gap types planned: low-income areas with poor access (equity gap, likely needs government intervention) vs. higher-income areas with poor access (market gap, an opportunity for private charging operators). The census tract/income data pipeline for this already exists in `scripts/build_ev_data.py`, just not wired into the app yet.
3. **Solar panel feasibility** — given an address, rooftop availability, and local weather data, estimate feasible solar capacity and expected yearly output. Not yet scoped.
