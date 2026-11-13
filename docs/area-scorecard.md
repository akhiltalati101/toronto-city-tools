# Should I Live Here?

Check any Toronto address for what's changing nearby, how it compares on safety, and — if it's a rental apartment — its official maintenance record. Three independent live lookups, no address-specific data pre-built ahead of time.

## How it works

1. **Zoning & development** — active City of Toronto planning applications within 400m, queried live against the [Application Information Centre](https://www.toronto.ca/city-government/planning-development/application-information-centre/)'s public map layer. Each application gets a plain-English summary on first view (via OpenRouter — by default a free model, overridable with `OPENROUTER_MODEL` — cached after that so repeat lookups are instant), or the city's own description text if summarization isn't configured, plus a link to the official application page.
2. **Safety** — Toronto Police's Community Safety Indicators (crime) data for the last 6 months within 500m, weighted by severity (weapons/robbery/break-ins count more than minor theft) and compared to what you'd expect for an area that size at the citywide rate.
3. **Rental building quality** — if the address looks like an apartment/condo building (via OpenStreetMap tags), its official [RentSafeTO](https://www.rentsafeto.com/) evaluation score, if it's a registered rental. RentSafeTO doesn't cover owner-occupied condo corporations — an unmatched multi-unit building gets an honest "likely a condo, not a missing data point" note and a Facebook group search link instead.

## Data sources

| Data | Source |
|---|---|
| Zoning/development applications | Live query against `gis.toronto.ca`'s ArcGIS layer behind the [Application Information Centre](https://www.toronto.ca/city-government/planning-development/application-information-centre/) map. The old open-data "Development Applications" dataset is retired — this hits the live layer directly. |
| Crime | [Toronto Police Community Safety Indicators](https://data.tps.ca/pages/community-safety-indicators) (formerly Major Crime Indicators), live ArcGIS FeatureServer. Locations are offset to the nearest intersection by TPS for privacy. |
| Rental building evaluations | [RentSafeTO Apartment Building Evaluation](https://open.toronto.ca/dataset/apartment-building-evaluation/), refreshed daily by the city |
| Building type (rental check) | [OpenStreetMap](https://www.openstreetmap.org/), queried live per address via [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) |

## Code & running locally

The scoring logic for this tool lives in `toronto_tools/area/` and is served by the API in `api/`; the UI is the `/area` page of the React app in `frontend/`. See the [README](../README.md) for the architecture and how to run both locally.

## Pre-warming the summary cache (optional)

`scripts/build_zoning_summaries.py` fetches active "Community planning"/"TLAB" applications from the last two years, diffs them against the previously-published summary cache (by description hash + staleness), and calls OpenRouter only for new, changed, or stale entries. This is **not required** — the app summarizes on demand regardless — but running it ahead of time means a popular address's first-ever view doesn't wait on a handful of live LLM calls. Trigger manually via `.github/workflows/rebuild-zoning-summaries.yml` (`workflow_dispatch`, no automatic schedule), which publishes the output as a GitHub Release asset under the `zoning-data` tag that the app checks first:

```bash
export OPENROUTER_API_KEY=...
python scripts/build_zoning_summaries.py --out build
```

Either path — the live app or this script — calls the same OpenRouter key, so cost is capped in exactly one place regardless: a **credit limit set directly on the OpenRouter API key**, in OpenRouter's dashboard. When the limit is hit, OpenRouter returns HTTP 402 and both paths fall back to the city's own raw description text.

## Limitations & things to sanity-check

- Zoning "Open" status is a data-quality quirk in places — some applications from the 1990s/2000s are still marked `STATUS_GROUP='Open'` in the source system. The live per-address query surfaces these as-is (sorted newest-first); the summary build script bounds itself to the last two years to avoid summarizing thousands of decades-old records.
- Safety comparison uses a simple radius/citywide-density ratio, not a population- or footfall-adjusted rate — busy commercial/entertainment districts will read as "less safe" partly because of pedestrian volume, not just risk. Treat the grade as directional.
- RentSafeTO matching is by nearest coordinates (falling back to normalized address matching) within 60m — a genuinely registered building just outside that radius (geocoding jitter) will show as unmatched rather than risk a wrong cross-building match.
- Rental building classification is the same OSM-tag heuristic as [ev-scorecard](ev-scorecard.md)'s home-charging check — building *form*, not a guarantee.

## Roadmap

1. **Should I Live Here?** *(this app, v1)* — zoning/development, safety, and rental building quality for a single address
2. **Reddit mentions (v1.1)** — narrow, official-API search (not scraping) for a specific building's address/name, surfaced alongside the RentSafeTO score or the Facebook group fallback
