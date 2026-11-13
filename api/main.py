"""FastAPI service behind the React frontend: wraps the three tools'
pipelines (toronto_tools/{city,ev,area}/pipeline.py) as JSON endpoints.

Each score endpoint takes either `address` (geocoded via Photon) or
`lat`+`lon` (a clicked map point), optionally both (the address is then just
the label). Validation problems (unknown address, outside Toronto) are 400s
with a human-readable `detail`; an upstream data service being down is a
502.

Configuration (environment variables):
  ALLOWED_ORIGINS     comma-separated CORS origins (the frontend's URL)
  RATE_LIMIT          per-IP limit on score endpoints, e.g. "20/minute"
  PRELOAD_DATA        "0" to skip loading datasets at startup (tests/dev)
  DATA_CACHE_DIR      where downloaded datasets are kept (see release_data.py)
  OPENROUTER_API_KEY  enables live plain-English zoning summaries
  OPENROUTER_MODEL    overrides the default (free) summarization model
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api import schemas, serialize
from toronto_tools.area import pipeline as area_pipeline
from toronto_tools.city import pipeline as city_pipeline
from toronto_tools.city.data import get_city_amenities, get_city_graph
from toronto_tools.city.scoring import PROFILES
from toronto_tools.common.nearest import warm
from toronto_tools.ev import pipeline as ev_pipeline
from toronto_tools.ev.data import get_charging_stations

log = logging.getLogger("toronto_tools.api")

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
RATE_LIMIT = os.environ.get("RATE_LIMIT", "20/minute")

_data_ready = threading.Event()


def _preload() -> None:
    """Load the city-wide datasets (~1.7 GB of graphs, ~30 s) and their
    spatial indexes before the first request needs them."""
    try:
        for network_type in ("walk", "bike"):
            warm(get_city_graph(network_type))
        get_city_amenities()
        get_charging_stations()
        _data_ready.set()
        log.info("Datasets loaded")
    except Exception:
        log.exception("Dataset preload failed; datasets will load on first request instead")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("PRELOAD_DATA", "1") != "0":
        threading.Thread(target=_preload, daemon=True).start()
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Toronto City Tools API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(requests.exceptions.RequestException)
async def _upstream_error(request: Request, exc: requests.exceptions.RequestException):
    log.warning("Upstream request failed: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": "A city data service didn't respond. Please try again in a moment."},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "data_ready": _data_ready.is_set()}


@app.get("/api/config")
def config():
    """Static scoring config the frontend needs before any score request."""
    return {"profiles": PROFILES}


@app.get("/api/city/score", response_model=schemas.CityScore)
@limiter.limit(RATE_LIMIT)
def city_score(
    request: Request,
    address: Optional[str] = None,
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    profile: str = "General",
):
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}; choose one of {', '.join(PROFILES)}.")
    return serialize.city(city_pipeline.run_scorecard(address, PROFILES[profile], lat=lat, lon=lon))


@app.get("/api/ev/score", response_model=schemas.EvScore)
@limiter.limit(RATE_LIMIT)
def ev_score(
    request: Request,
    address: Optional[str] = None,
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
):
    return serialize.ev(ev_pipeline.run_scorecard(address, lat=lat, lon=lon))


@app.get("/api/area/score", response_model=schemas.AreaScore)
@limiter.limit(RATE_LIMIT)
def area_score(
    request: Request,
    address: Optional[str] = None,
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
):
    return serialize.area(area_pipeline.run_scorecard(address, lat=lat, lon=lon))
