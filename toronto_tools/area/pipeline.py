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
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from cachetools import TTLCache, cached

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


@lru_cache(maxsize=4096)
def _cached_live_summary(application_number: str, description_hash: str, description: str, api_key: str) -> Optional[str]:
    """Live, on-demand summary for one application, cached for the life of
    this process (no ttl) — a repeat lookup of the same application by
    anyone else's request in this process never re-calls the LLM.
    description_hash is part of the cache key purely so a changed
    description naturally busts the cache; the LLM call itself uses
    `description`."""
    global _spend_cap_reached
    if _spend_cap_reached:
        return None
    try:
        return llm_summarize(description, api_key)
    except SpendCapReached:
        _spend_cap_reached = True
        return None
    except Exception:
        return None  # network hiccup, timeout, etc. — fall back to raw description rather than fail the page


def _enrich_zoning(applications: list[ZoningApplication], summaries: dict, api_key: Optional[str]) -> list[ZoningApplicationDisplay]:
    enriched = []
    for app in applications:
        cached = summaries.get(app.application_number)
        summary = cached["summary"] if cached else None

        if summary is None and api_key and app.description:
            summary = _cached_live_summary(
                app.application_number, _hash_description(app.description), app.description, api_key,
            )

        display_text = summary or app.description or "No description provided by the city for this application."
        enriched.append(ZoningApplicationDisplay(application=app, summary=summary, display_text=display_text))
    return enriched


def run_scorecard(address: Optional[str], lat: Optional[float] = None, lon: Optional[float] = None) -> AreaScorecard:
    """Run the full pipeline for a single address (or a map point if lat/lon
    are given): locate once, then the three independent lookups
    (zoning/safety/rental).

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from resolve_location).
    """
    address, lat, lon = resolve_location(address, lat, lon)

    applications = query_nearby_applications(lat, lon)
    summaries = get_zoning_summaries()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    zoning_display = _enrich_zoning(applications, summaries, api_key)

    citywide_total = _cached_citywide_weighted_total()
    safety_result = score_safety(lat, lon, citywide_total)

    rentsafe_df = get_rentsafe_data()
    rental_result = check_rental(lat, lon, address, rentsafe_df)

    return AreaScorecard(
        address=address, lat=lat, lon=lon,
        zoning_applications=zoning_display,
        safety=safety_result,
        rental=rental_result,
    )

