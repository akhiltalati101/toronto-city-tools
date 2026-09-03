"""Downloads and holds prebuilt/external data used by the app:

- Zoning application summaries: a small {application_number: {summary,
  description_hash, last_updated_date}} JSON published to GitHub Releases by
  scripts/build_zoning_summaries.py (rebuilt on a schedule by
  .github/workflows/rebuild-zoning-summaries.yml), same fixed-release-tag
  pattern as ev-scorecard/data.py's charger/graph downloads. If the release
  doesn't exist yet (e.g. before the workflow has ever run) this returns an
  empty dict rather than failing — zoning.py already falls back to each
  application's raw city-provided description when no summary is cached, so
  a missing file behaves exactly like "not summarized yet."

- RentSafeTO apartment building evaluations: downloaded directly from
  open.toronto.ca (the city already refreshes it daily), with a matching TTL
  cache — no rebuild pipeline needed for this one.
"""
import io

import pandas as pd
import requests
import streamlit as st

ZONING_DATA_RELEASE_URL = (
    "https://github.com/akhiltalati101/toronto-city-tools/releases/download/zoning-data"
)
ZONING_SUMMARIES_ASSET = "zoning_summaries.json"

RENTSAFE_CSV_URL = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "4ef82789-e038-44ef-a478-a8f3590c3eb1/resource/"
    "7fa98ab2-7412-43cd-9270-cb44dd75b573/download/"
    "apartment-building-evaluations-2023-current.csv"
)


@st.cache_resource(show_spinner="Loading zoning application summaries...")
def get_zoning_summaries() -> dict:
    """Return {application_number: {"summary": str, "description_hash": str,
    "last_updated_date": str}}. Empty dict if the release/asset doesn't
    exist yet — callers should treat that the same as "no summary cached
    for this application"."""
    url = f"{ZONING_DATA_RELEASE_URL}/{ZONING_SUMMARIES_ASSET}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        return {}


@st.cache_data(ttl=86400, show_spinner="Loading RentSafeTO building evaluations...")
def get_rentsafe_data() -> pd.DataFrame:
    """Return the RentSafeTO apartment building evaluation table (2023-current),
    re-downloaded daily since the city refreshes it daily. Columns include
    SITE ADDRESS, LATITUDE, LONGITUDE, CURRENT BUILDING EVAL SCORE,
    EVALUATION COMPLETED ON, CONFIRMED STOREYS/UNITS, PROPERTY TYPE, and one
    column per inspected category (scored 1-3, or "N/A")."""
    resp = requests.get(RENTSAFE_CSV_URL, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df["LATITUDE"] = pd.to_numeric(df["LATITUDE"], errors="coerce")
    df["LONGITUDE"] = pd.to_numeric(df["LONGITUDE"], errors="coerce")
    return df
