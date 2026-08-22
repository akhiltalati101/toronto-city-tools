# EV Charging Scorecard

Check any address in Toronto for whether it's **underserved or overserved** by public EV charging — not just "how close is the nearest charger," but how the local supply compares to what the neighbourhood actually needs, adjusted for income.

## How it works

Enter an address → the app locates its Statistics Canada **census tract** and compares:

- **Local supply** — public charging ports in that tract, per 1,000 residents
- **Citywide benchmark** — the citywide average ports-per-1,000-residents, adjusted by the tract's **median household income percentile**

Lower-income tracts are held to a *higher* expected supply bar, not a lower one — the working assumption is that scarce public charging is itself a barrier to EV adoption in those areas, rather than a sign of lower need. This is a modeling choice, not a neutral fact; it's exposed in the app as an "equity weighting" slider (0 = income-blind ratio) so it can be tuned or turned off.

**Supply index** = local ratio ÷ income-adjusted benchmark. Below 1.0 means underserved relative to the benchmark; above 1.0 means overserved. Results bucket into five labels: Strongly Underserved, Underserved, Balanced, Overserved, Strongly Overserved.

## Data sources

| Data | Source |
|---|---|
| Charging stations | [City of Toronto Open Data](https://open.toronto.ca/dataset/city-operated-electric-vehicle-charging-station-map/) — city-operated public EV charging stations, refreshed quarterly. Covers city-operated (Green P) stations only, not private-network chargers (e.g. mall/condo/workplace chargers), so it undercounts total real-world access. |
| Census tract boundaries | Statistics Canada 2021 [Cartographic Boundary Files](https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm) |
| Population + median household income | Statistics Canada 2021 [Census Profile](https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/index.cfm) |

## Stack

| Layer | Choice |
|---|---|
| **Core** | Python + [GeoPandas](https://geopandas.org/) |
| **Maps** | [Folium](https://python-visualization.github.io/folium/) |
| **UI** | [Streamlit](https://streamlit.io/) |

## Project structure

```
ev-scorecard/
├── geocode.py          # Address → (lat, lon) via Photon
├── data.py             # Downloads/caches prebuilt charger + census tract data
├── supply_demand.py    # Locates a tract, computes the income-adjusted supply index
├── pipeline.py         # geocode -> locate tract -> score, bundled for reuse
├── mapview.py          # Folium map: tract boundary, chargers, supply-index badge
├── app.py              # Streamlit UI — the app entry point
├── scripts/
│   └── build_ev_data.py  # Offline build: fetches + joins all three data sources
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

The first request downloads the prebuilt charger + census tract data from GitHub Releases (published by `scripts/build_ev_data.py`, see below) and caches it for the life of the process.

## Rebuilding the data

`scripts/build_ev_data.py` fetches and joins all three data sources into two GeoParquet files. It's run periodically by `.github/workflows/rebuild-ev-data.yml` (quarterly — charging stations and census data both change slowly), which publishes the output as GitHub Release assets under the `ev-data` tag:

```bash
python scripts/build_ev_data.py --out build
```

## Limitations & things to sanity-check

- The city-operated charging station dataset doesn't include private-network chargers, so raw port counts understate real-world charging access everywhere — the supply index should be read as relative (which tracts have more/less city-provided supply than others), not absolute.
- The income-adjustment formula is a modeling choice: it treats low income as *increasing* expected need for public charging, on the theory that scarce charging suppresses EV adoption in those areas rather than reflecting lower demand. Worth validating against known neighbourhoods before trusting results, and worth discussing whether this framing matches the intended use of the tool.
- Census tracts near Toronto's edge may have chargers or population that fall just outside this app's coverage; addresses far from downtown are more likely to hit tract-boundary edge effects.

## Roadmap

1. **EV Charging Scorecard** *(this app)* — supply/demand/income-based under/overserved score per address
2. **Solar panel feasibility** — given an address, rooftop availability, and local weather data, estimate feasible solar capacity and expected yearly output. Not yet scoped: data sources for rooftop geometry/orientation and solar irradiance are still open questions.
