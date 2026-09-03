#!/usr/bin/env python3
"""Build plain-English summaries of active zoning/development applications.

This is an OPTIONAL pre-warm tool, not the primary summarization path. The
app itself now summarizes applications live, on first view, and caches the
result for the life of the running process (see pipeline.py's use of
llm_summary.summarize) — cost is capped the same way either path calls
OpenRouter: a hard credit limit on the API key itself, set in OpenRouter's
dashboard, not enforced by any code here. This script exists for citywide
backfill/pre-warming (so a popular address's zoning section doesn't wait on
a handful of live LLM calls on its first-ever view) — trigger manually via
`workflow_dispatch` in .github/workflows/rebuild-zoning-summaries.yml, which
uploads the output as a GitHub Release asset under the fixed "zoning-data"
tag (same pattern as ev-scorecard's rebuild-ev-data.yml). data.py downloads
from that fixed URL and pipeline.py checks it first, before falling back to
a live call.

Scope: only "Community planning" and "TLAB" applications from the last two
years are considered for summarization. Two reasons: (1) these are the
folder types with rich FOLDERDESCRIPTION text worth summarizing — Minor
Variance / Committee of Adjustment applications are usually one-line
property tweaks with no description at all (confirmed by sampling the live
API); (2) the AIC layer has ~9,400 rows still marked STATUS_GROUP='Open'
going back to the 1990s (a data-quality quirk of the source system, not
actually "active" in any useful sense), so an unbounded citywide sweep would
summarize thousands of decades-old applications nobody will ever look up.

Incremental by design: each cached entry stores a hash of the source
description and a last_updated_date. A summary is only (re)generated when
the application is new, its description changed, or the cached summary is
older than STALENESS_DAYS — so after the first backfill, daily runs only
touch a handful of genuinely new/changed applications.

Usage:
  export OPENROUTER_API_KEY=...
  python scripts/build_zoning_summaries.py --out build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_summary import SpendCapReached, summarize  # noqa: E402

AIC_FEATURESERVER_URL = (
    "https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/FeatureServer/60/query"
)
ZONING_DATA_RELEASE_URL = (
    "https://github.com/akhiltalati101/toronto-city-tools/releases/download/zoning-data"
)
ZONING_SUMMARIES_ASSET = "zoning_summaries.json"

MAJOR_APPLICATION_TYPES = ("Community planning", "TLAB")
MIN_FOLDERYEAR = str(datetime.now(timezone.utc).year - 2)[-2:]  # e.g. "24" for 2026-2=2024
STALENESS_DAYS = 90
PAGE_SIZE = 2000

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "build"


def fetch_applications() -> list[dict]:
    """Paginate the AIC FeatureServer for open, major-type, recent applications.
    Returns one row per application_number (deduplicated; multi-parcel
    applications repeat one row per address in the source layer)."""
    type_list = ",".join(f"'{t}'" for t in MAJOR_APPLICATION_TYPES)
    where = f"STATUS_GROUP='Open' AND APPLICATION_TYPE IN ({type_list}) AND FOLDERYEAR>='{MIN_FOLDERYEAR}'"

    by_number: dict[str, dict] = {}
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": "APPLICATION_NUMBER,FOLDERDESCRIPTION",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "f": "json",
        }
        resp = requests.get(AIC_FEATURESERVER_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"AIC service error: {data['error']}")

        features = data.get("features", [])
        for feature in features:
            attrs = feature["attributes"]
            number = attrs.get("APPLICATION_NUMBER")
            if number and number not in by_number:
                by_number[number] = attrs

        print(f"[fetch] offset={offset} -> {len(features)} rows ({len(by_number)} unique applications so far)")
        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return list(by_number.values())


def _hash_description(description: str) -> str:
    return hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]


def load_existing_summaries() -> dict:
    url = f"{ZONING_DATA_RELEASE_URL}/{ZONING_SUMMARIES_ASSET}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"[cache] loaded {len(data)} existing summaries from {url}")
        return data
    except requests.exceptions.RequestException as e:
        print(f"[cache] no existing summaries found ({e}) — starting fresh")
        return {}


def needs_summary(number: str, description_hash: str, existing: dict) -> bool:
    cached = existing.get(number)
    if cached is None:
        return True
    if cached.get("description_hash") != description_hash:
        return True
    last_updated = cached.get("last_updated_date")
    if not last_updated:
        return True
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(last_updated)
    except ValueError:
        return True
    return age > timedelta(days=STALENESS_DAYS)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-calls", type=int, default=None, help="Cap the number of LLM calls this run (for local testing)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[warn] OPENROUTER_API_KEY not set — no new summaries will be generated this run.")

    applications = fetch_applications()
    existing = load_existing_summaries()

    summaries = dict(existing)
    calls_made = 0
    skipped_cap = 0

    for attrs in applications:
        number = attrs["APPLICATION_NUMBER"]
        description = (attrs.get("FOLDERDESCRIPTION") or "").strip()
        if not description:
            continue  # nothing to summarize; app falls back to its own "no description" text

        description_hash = _hash_description(description)
        if not needs_summary(number, description_hash, existing):
            continue

        if not api_key:
            skipped_cap += 1
            continue
        if args.max_calls is not None and calls_made >= args.max_calls:
            skipped_cap += 1
            continue

        try:
            summary_text = summarize(description, api_key)
        except SpendCapReached:
            print("[cap] OpenRouter credit limit reached — stopping summarization for this run.")
            skipped_cap += len(applications) - calls_made
            break
        except requests.exceptions.RequestException as e:
            print(f"[warn] summarization failed for {number}: {e}")
            continue

        calls_made += 1
        if summary_text:
            summaries[number] = {
                "summary": summary_text,
                "description_hash": description_hash,
                "last_updated_date": datetime.now(timezone.utc).isoformat(),
            }
        time.sleep(0.2)  # polite pacing, not a rate-limit workaround

    print(f"[summarize] {calls_made} LLM calls made, {skipped_cap} applications left for a future run, "
          f"{len(summaries)} total cached summaries")

    out_path = args.out / ZONING_SUMMARIES_ASSET
    with open(out_path, "w") as f:
        json.dump(summaries, f, indent=2)
    print(f"[save] {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
