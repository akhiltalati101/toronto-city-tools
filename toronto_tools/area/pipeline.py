"""Bundles the geocode -> zoning/safety/rental lookups into a single call,
used by the API's /area/score endpoint — same shape as ev/pipeline.py.

The citywide crime baseline (safety.query_citywide_weighted_total) is the
one piece cached here rather than in safety.py itself: it's identical for
every address in a given day, so it's wasteful to recompute per request, but
safety.py is kept free of caching concerns (importable and testable
standalone).
"""
from __future__ import annotations

import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from cachetools import LRUCache, TTLCache, cached

from toronto_tools.area.data import get_rentsafe_data, get_zoning_summaries
from toronto_tools.area.llm_summary import SpendCapReached
from toronto_tools.area.llm_summary import summarize as llm_summarize
from toronto_tools.area.rental import RentalResult, check_rental
from toronto_tools.area.safety import SafetyResult, query_citywide_weighted_total, score_safety
from toronto_tools.area.zoning import ZoningApplication, query_nearby_applications
from toronto_tools.common.geocode import resolve_location

# Set for the rest of this process once OpenRouter returns 402 (the API
# key's credit limit is hit), so further uncached applications fall straight
# back to raw description text instead of making a network round-trip that's
# guaranteed to fail the same way.
_spend_cap_reached = False

# Kept low: free OpenRouter models share a rate-limited pool across users.
SUMMARY_WORKERS = 4


@dataclass
class ZoningApplicationDisplay:
    application: ZoningApplication
    summary: Optional[str]       # plain-English summary if cached, else None
    display_text: str            # summary if available, otherwise the raw city description (or a placeholder)


@dataclass
class AreaScorecard:
    address: str
    lat: float
    lon: float
    zoning_applications: list[ZoningApplicationDisplay]
    safety: SafetyResult
    rental: RentalResult


@cached(TTLCache(maxsize=1, ttl=86400), lock=threading.Lock())
def _cached_citywide_weighted_total() -> float:
    return query_citywide_weighted_total()


def _hash_description(description: str) -> str:
    return hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]


_summary_cache: LRUCache = LRUCache(maxsize=4096)
_summary_cache_lock = threading.Lock()


def _cached_live_summary(application_number: str, description_hash: str, description: str, api_key: str) -> Optional[str]:
    """Live, on-demand summary for one application, cached for the life of
    this process (no ttl) — a repeat lookup of the same application by
    anyone else's request never re-calls the LLM. description_hash is part
    of the cache key purely so a changed description naturally busts the
    cache. Failed calls (network hiccup, free-tier 429) aren't cached, so
    the next request for that application retries."""
    global _spend_cap_reached
    key = (application_number, description_hash)
    with _summary_cache_lock:
        if key in _summary_cache:
            return _summary_cache[key]
    if _spend_cap_reached:
        return None
    try:
        summary = llm_summarize(description, api_key)
    except SpendCapReached:
        _spend_cap_reached = True
        return None
    except Exception:
        return None  # fall back to raw description rather than fail the page
    with _summary_cache_lock:
        _summary_cache[key] = summary
    return summary


def _enrich_one(app: ZoningApplication, summaries: dict, api_key: Optional[str]) -> ZoningApplicationDisplay:
    cached = summaries.get(app.application_number)
    summary = cached["summary"] if cached else None

    if summary is None and api_key and app.description:
        summary = _cached_live_summary(
            app.application_number, _hash_description(app.description), app.description, api_key,
        )

    display_text = summary or app.description or "No description provided by the city for this application."
    return ZoningApplicationDisplay(application=app, summary=summary, display_text=display_text)


def _enrich_zoning(applications: list[ZoningApplication], summaries: dict, api_key: Optional[str]) -> list[ZoningApplicationDisplay]:
    # Uncached summaries are live LLM calls of up to a few seconds each, so
    # they run concurrently rather than one after another.
    with ThreadPoolExecutor(max_workers=SUMMARY_WORKERS) as pool:
        return list(pool.map(lambda app: _enrich_one(app, summaries, api_key), applications))


def _zoning(lat: float, lon: float) -> list[ZoningApplicationDisplay]:
    applications = query_nearby_applications(lat, lon)
    return _enrich_zoning(applications, get_zoning_summaries(), os.environ.get("OPENROUTER_API_KEY"))


def _safety(lat: float, lon: float) -> SafetyResult:
    return score_safety(lat, lon, _cached_citywide_weighted_total())


def run_scorecard(address: Optional[str], lat: Optional[float] = None, lon: Optional[float] = None) -> AreaScorecard:
    """Run the full pipeline for a single address (or a map point if lat/lon
    are given): locate once, then the three independent lookups
    (zoning/safety/rental), concurrently since each is a live network call.

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from resolve_location).
    """
    address, lat, lon = resolve_location(address, lat, lon)

    with ThreadPoolExecutor(max_workers=3) as pool:
        zoning = pool.submit(_zoning, lat, lon)
        safety = pool.submit(_safety, lat, lon)
        rental = pool.submit(lambda: check_rental(lat, lon, address, get_rentsafe_data()))

        return AreaScorecard(
            address=address, lat=lat, lon=lon,
            zoning_applications=zoning.result(),
            safety=safety.result(),
            rental=rental.result(),
        )
