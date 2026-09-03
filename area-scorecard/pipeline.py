"""Bundles the geocode -> zoning/safety/rental lookups into a single call,
shared by app.py — same shape as ev-scorecard/pipeline.py.

The citywide crime baseline (safety.query_citywide_weighted_total) is the
one piece cached here rather than in safety.py itself: it's identical for
every address in a given day, so it's wasteful to recompute per request, but
safety.py is kept framework-agnostic (no streamlit import, importable and
testable standalone) — the streamlit-specific caching lives here instead,
where app.py's other orchestration already depends on streamlit anyway.
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from data import get_rentsafe_data, get_zoning_summaries
from geocode import geocode_address
from llm_summary import SpendCapReached
from llm_summary import summarize as llm_summarize
from rental import RentalResult, check_rental
from safety import SafetyResult, query_citywide_weighted_total, score_safety
from zoning import ZoningApplication, query_nearby_applications

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


@st.cache_data(ttl=86400, show_spinner=False)
def _cached_citywide_weighted_total() -> float:
    return query_citywide_weighted_total()


def _hash_description(description: str) -> str:
    return hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]


@st.cache_data(show_spinner=False)
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


def run_scorecard(address: str) -> AreaScorecard:
    """Run the full pipeline for a single address: geocode once, then the
    three independent lookups (zoning/safety/rental).

    Raises ValueError if the address can't be geocoded or falls outside the
    supported Toronto area (propagated from geocode_address).
    """
    lat, lon = geocode_address(address)

    applications = query_nearby_applications(lat, lon)
    summaries = get_zoning_summaries()
    api_key = st.secrets.get("OPENROUTER_API_KEY")
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


if __name__ == "__main__":
    for address in ("100 Queen St W", "35 Playter Blvd"):
        card = run_scorecard(address)
        print(f"\n=== {address} ===")
        print(f"  {len(card.zoning_applications)} nearby zoning applications")
        print(f"  safety: {card.safety.grade} (ratio {card.safety.ratio})")
        print(f"  rental: apartment={card.rental.building.is_apartment}, "
              f"matched={card.rental.rentsafe is not None}")
