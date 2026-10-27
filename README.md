# Toronto City Tools

Tools to help citizens of Toronto stay more informed and participate in city-related decisions.

| Tool | What it answers |
|---|---|
| **City Scorecard** (`/city`) | How well does this address meet the 15-minute city standard — groceries, healthcare, parks, schools, transit, fitness? ([details](docs/city-scorecard.md)) |
| **Should I Own an EV?** (`/ev`) | How well is it served by public charging my car can plug into, and can it likely take a home charger? ([details](docs/ev-scorecard.md)) |
| **Should I Live Here?** (`/area`) | What's being built nearby, how does it compare on safety, and how well maintained is the building if it's a rental? ([details](docs/area-scorecard.md)) |

See [PROJECTS.md](PROJECTS.md) for a longer write-up of each tool.

## Architecture

```
frontend/        React + TypeScript (Vite) — static site, deploys to Vercel
   │  GET /api/{city,ev,area}/score?address=…  or  ?lat=…&lon=…
   ▼
api/             FastAPI — thin HTTP layer: validation, rate limiting, JSON/GeoJSON
   │
toronto_tools/   The scoring logic, framework-free
   ├── city/       amenities, 15-min walk/bike isochrones, weighted score
   ├── ev/         charger access by connector, home-charging check
   ├── area/       zoning applications, crime comparison, RentSafeTO, LLM summaries
   └── common/     geocoding, isochrones, OSM building lookup, dataset downloads
scripts/         Offline dataset builders, run by .github/workflows/rebuild-*.yml
```

The API keeps two citywide street graphs (walk + bike, from OpenStreetMap) in memory: about **1.9 GB of RAM** and ~30 s to load at startup. That's why it runs as an always-on server rather than serverless functions. The datasets are prebuilt by the `rebuild-*` workflows, published as GitHub Release assets, and downloaded by the API on first start (cached in `DATA_CACHE_DIR`). Everything else (geocoding, crime, zoning, RentSafeTO, building footprints) is queried live per request.

Two small pieces of scoring also run in the browser, so the weight sliders and EV connector checkboxes re-score instantly without a request: `frontend/src/lib/scoring.ts` mirrors `apply_weights` and `score_from_walk_times`. Both sides are tested against the same fixture, `tests/fixtures/scoring_cases.json`, so they can't drift apart.

## Running locally

**Prerequisites:** Python 3.11+, Node 22+. On macOS the built-in `python3` is 3.9 with an old pip, which can't install this project — install a newer one first (e.g. `brew install python@3.12`) and check `python --version` inside the venv.

```bash
# API — first start downloads ~250 MB of datasets into .data_cache/
python3.12 -m venv .venv && source .venv/bin/activate   # any Python 3.11+
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn api.main:app --reload --port 8000

# Frontend (second terminal) — proxies /api to localhost:8000
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Optional environment variables for the API:

| Variable | Default | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS origins — set to your frontend's URL in production |
| `RATE_LIMIT` | `20/minute` | Per-IP limit on the score endpoints |
| `DATA_CACHE_DIR` | `.data_cache/` | Where downloaded datasets are kept |
| `OPENROUTER_API_KEY` | — | Enables live plain-English zoning summaries ([get a key](https://openrouter.ai/keys); cap spend with a credit limit on the key). Without it, the city's raw description is shown. |
| `OPENROUTER_MODEL` | a free model | Override the summarization model |
| `PRELOAD_DATA` | `1` | `0` skips loading datasets at startup (they load on first request instead) |

The frontend reads `VITE_API_URL` (the API's base URL) at build time; leave it unset locally.

### Tests

```bash
pytest                                   # API + scoring logic
cd frontend && npm run lint && npm run typecheck && npm test
```

CI (`.github/workflows/ci.yml`) runs both on every pull request.

## Deploying

**API → Fly.io** (or any Docker host with ≥3 GB RAM). `fly.toml` and the `Dockerfile` are ready:

```bash
fly launch --no-deploy --copy-config
fly volumes create data --size 1 --region yyz
fly secrets set ALLOWED_ORIGINS=https://<your-app>.vercel.app OPENROUTER_API_KEY=...
fly deploy
```

On your own server: `docker build -t toronto-city-tools-api . && docker run -d -p 8000:8000 -v tct-data:/data -e ALLOWED_ORIGINS=https://… toronto-city-tools-api`, behind a reverse proxy that terminates HTTPS.

**Frontend → Vercel.** Import the repo, set the **Root Directory** to `frontend`, and add the environment variable `VITE_API_URL=https://<your-api-host>`. `frontend/vercel.json` handles client-side routing. Any static host works: `npm run build` emits `frontend/dist/`.

**Data refreshes** need no deploy. The `rebuild-*` workflows republish the release assets on their schedule. Clear `DATA_CACHE_DIR` (or the Fly volume) and restart the API to pick up new data.

## License

See [LICENSE.md](LICENSE.md).
