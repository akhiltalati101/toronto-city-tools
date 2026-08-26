#!/usr/bin/env python3
"""Build the census-tract-level EV charging supply/demand/income dataset.

Replaces per-address live API calls in supply_demand.py with a one-time
(periodic) bulk build. Run manually, or on a schedule via
.github/workflows/rebuild-ev-data.yml, which uploads the output artifacts as
GitHub Release assets for the app to download at startup (see data.py).

Three data sources, all fetched live by this script (no manual downloads):

1. Charging stations — NREL's Alternative Fuel Stations API (the DOE/AFDC
   database), covering all public *and* private-access EV charging in
   Ontario, not just City of Toronto-operated ones. Requires an NREL_API_KEY
   env var (free key from https://developer.nlr.gov/signup/). The API has no
   bounding-box parameter, so we fetch all of Ontario and clip to GTA_BBOX
   locally. Wider than TORONTO_BBOX below (used for census tracts) since this
   part of the pipeline is cheap to run at GTA scope even though walkability
   scoring in the app itself is still Toronto-only for now.

2. Census tract boundaries — Statistics Canada's 2021 Cartographic Boundary
   Files, served live via an ArcGIS REST MapServer (no shapefile download
   needed), queried by bounding box.

3. Census tract population + income — Statistics Canada's 2021 Census
   Profile bulk CSV (catalogue 98-401-X2021007, "Canada, provinces,
   territories, CMAs, tracted CAs and census tracts"). This is a ~2.6 GB
   "tall" CSV (one row per geography x characteristic) inside a ~250 MB zip.
   We stream it once, keeping only rows for our target census tracts and the
   two characteristics we need:
     - CHARACTERISTIC_ID 1   = "Population, 2021"
     - CHARACTERISTIC_ID 243 = "Median total income of household in 2020 ($)"
   These IDs were confirmed against the file's accompanying meta file and a
   sample row; if StatCan ever reorders the profile table these IDs would
   need re-verifying (see CHARACTERISTIC_NAME assertions below, which fail
   loudly rather than silently mis-scoring tracts).

Usage:
  python scripts/build_ev_data.py             # full build
  python scripts/build_ev_data.py --out build
"""
import argparse
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

# Generous City of Toronto bounding box: (minx, miny, maxx, maxy) — mirrors
# geocode.py's TORONTO_BBOX. Used for census tracts (and, historically, the
# charging-station fetch) — everything downstream of this bbox is what the
# app can actually score today.
TORONTO_BBOX = (-79.64, 43.58, -79.11, 43.86)

# Generous Greater Toronto Area bounding box: (minx, miny, maxx, maxy) —
# covers Halton, Peel, City of Toronto, York, and Durham regions. Used only
# for the charging-station fetch (see fetch_charging_stations) since that
# data is free to pull at GTA scope; walkability scoring elsewhere in the
# pipeline is still clipped to TORONTO_BBOX.
GTA_BBOX = (-80.00, 43.15, -78.55, 44.35)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "build"

NREL_API_URL = "https://developer.nlr.gov/api/alt-fuel-stations/v1.json"

CT_BOUNDARY_SERVICE = (
    "https://geo.statcan.gc.ca/geo_wa/rest/services/2021/"
    "Cartographic_boundary_files/MapServer/11/query"
)

CENSUS_PROFILE_ZIP_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/"
    "download-telecharger/comp/GetFile.cfm?Lang=E&FILETYPE=CSV&GEONO=007"
)
CENSUS_PROFILE_CSV_MEMBER = "98-401-X2021007_English_CSV_data.csv"
CHARACTERISTIC_POPULATION = 1
CHARACTERISTIC_MEDIAN_HH_INCOME = 243
EXPECTED_NAME_POPULATION = "population, 2021"
EXPECTED_NAME_INCOME = "median total income of household in 2020"


# ---------------------------------------------------------------------------
# 1. Charging stations (NREL Alternative Fuel Stations API)
# ---------------------------------------------------------------------------

def fetch_charging_stations(bbox: tuple = GTA_BBOX) -> gpd.GeoDataFrame:
    """Fetch public and private-access EV charging stations in Ontario from
    NREL's Alternative Fuel Stations API, then clip to bbox locally (the API
    has no bounding-box parameter).

    access_code ("public"/"private"/"unknown") is kept as a column so
    downstream scoring can count public stations only while still surfacing
    private/restricted ones with a note.
    """
    api_key = os.environ.get("NREL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NREL_API_KEY environment variable is required (free key from "
            "https://developer.nlr.gov/signup/)."
        )

    print("[chargers] querying NREL Alternative Fuel Stations API (country=CA, state=ON, fuel_type=ELEC)")
    params = {
        "api_key": api_key,
        "fuel_type": "ELEC",
        "country": "CA",
        "state": "ON",
        "status": "E",  # available only — drop planned/temporarily-unavailable stations
        "access": "all",  # keep public and private; access_code lets downstream code filter
        "limit": "all",
    }
    resp = requests.get(NREL_API_URL, params=params, timeout=120)
    resp.raise_for_status()
    stations = resp.json().get("fuel_stations", [])
    print(f"[chargers] {len(stations):,} available ELEC stations in Ontario")

    df = pd.DataFrame(stations)
    minx, miny, maxx, maxy = bbox
    df = df[df["longitude"].between(minx, maxx) & df["latitude"].between(miny, maxy)]
    print(f"[chargers] {len(df):,} within GTA bounding box")

    df["level2_ports"] = pd.to_numeric(df["ev_level2_evse_num"], errors="coerce").fillna(0).astype(int)
    df["level3_ports"] = pd.to_numeric(df["ev_dc_fast_num"], errors="coerce").fillna(0).astype(int)
    df["total_ports"] = df["level2_ports"] + df["level3_ports"]
    df["address"] = df["street_address"]
    df["network"] = df["ev_network"]
    df["access_code"] = df["access_code"].fillna("unknown")

    gdf = gpd.GeoDataFrame(
        df[["address", "network", "level2_ports", "level3_ports", "total_ports", "access_code"]],
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return gdf


# ---------------------------------------------------------------------------
# 2. Census tract boundaries (StatCan ArcGIS REST, queried by bbox)
# ---------------------------------------------------------------------------

def fetch_census_tract_boundaries(bbox: tuple) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bbox
    params = {
        "where": "1=1",
        "geometry": json.dumps({
            "xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
            "spatialReference": {"wkid": 4326},
        }),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CTUID,DGUID,CTNAME,PRUID",
        "outSR": 4326,
        "resultRecordCount": 2000,
        # Generalizes geometry to ~20m tolerance — full-resolution polygons for
        # the whole bbox are ~12MB and occasionally 504 at the server's gateway;
        # this is plenty precise for point-in-polygon tract lookups and cuts the
        # response to a few hundred KB.
        "maxAllowableOffset": 0.0002,
        "f": "geojson",
    }
    print("[boundaries] querying StatCan census tract boundary service")
    fc = None
    for attempt in range(3):
        try:
            resp = requests.get(CT_BOUNDARY_SERVICE, params=params, timeout=60)
            resp.raise_for_status()
            fc = resp.json()
            break
        except (requests.exceptions.HTTPError, requests.exceptions.Timeout) as e:
            print(f"[boundaries] attempt {attempt + 1} failed ({e}), retrying...")
    if fc is None:
        raise RuntimeError("Census tract boundary service failed after 3 attempts.")

    if fc.get("properties", {}).get("exceededTransferLimit"):
        raise RuntimeError(
            "Census tract query exceeded the server's result limit — "
            "narrow TORONTO_BBOX or add pagination via resultOffset."
        )

    records = [
        {**f["properties"], "geometry": shape(f["geometry"])}
        for f in fc["features"]
    ]
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf = gdf.rename(columns={"CTUID": "ct_uid", "DGUID": "dguid", "CTNAME": "ct_name"})
    print(f"[boundaries] {len(gdf):,} census tracts in bounding box")
    return gdf[["ct_uid", "dguid", "ct_name", "geometry"]]


# ---------------------------------------------------------------------------
# 3. Population + income (StatCan 2021 Census Profile bulk CSV)
# ---------------------------------------------------------------------------

def fetch_census_profile(target_dguids: set, work_dir: Path) -> pd.DataFrame:
    """Stream the national Census Profile CSV, keeping only our target DGUIDs'
    population and median household income rows.

    Downloads the ~250 MB zip once (cached in work_dir), then streams the
    ~2.6 GB member CSV directly out of the zip without extracting it to disk.
    """
    zip_path = work_dir / "census_profile.zip"
    if not zip_path.exists():
        print(f"[profile] downloading {CENSUS_PROFILE_ZIP_URL}")
        work_dir.mkdir(parents=True, exist_ok=True)
        with requests.get(CENSUS_PROFILE_ZIP_URL, stream=True, timeout=600) as r:
            r.raise_for_status()
            tmp = zip_path.with_suffix(".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.rename(zip_path)
    else:
        print(f"[profile] reusing cached {zip_path}")

    wanted_ids = {CHARACTERISTIC_POPULATION, CHARACTERISTIC_MEDIAN_HH_INCOME}
    rows = []
    name_seen = {}

    print("[profile] streaming national profile CSV (this takes a few minutes)...")
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(CENSUS_PROFILE_CSV_MEMBER) as raw:
            text_stream = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            reader = pd.read_csv(
                text_stream,
                usecols=["DGUID", "CHARACTERISTIC_ID", "CHARACTERISTIC_NAME", "C1_COUNT_TOTAL"],
                dtype={"DGUID": str, "CHARACTERISTIC_ID": int, "CHARACTERISTIC_NAME": str},
                chunksize=500_000,
            )
            for chunk in reader:
                match = chunk[
                    chunk["DGUID"].isin(target_dguids) & chunk["CHARACTERISTIC_ID"].isin(wanted_ids)
                ]
                if not match.empty:
                    rows.append(match)
                    for _, r in match.iterrows():
                        name_seen.setdefault(r["CHARACTERISTIC_ID"], r["CHARACTERISTIC_NAME"].strip().lower())

    if not rows:
        raise RuntimeError("No matching rows found in the Census Profile CSV — check target DGUIDs.")

    profile = pd.concat(rows, ignore_index=True)
    print(f"[profile] matched {len(profile):,} rows across {profile['DGUID'].nunique():,} tracts")

    seen_pop_name = name_seen.get(CHARACTERISTIC_POPULATION, "")
    seen_income_name = name_seen.get(CHARACTERISTIC_MEDIAN_HH_INCOME, "")
    if EXPECTED_NAME_POPULATION not in seen_pop_name:
        raise RuntimeError(
            f"CHARACTERISTIC_ID {CHARACTERISTIC_POPULATION} no longer matches "
            f"'{EXPECTED_NAME_POPULATION}' (got {seen_pop_name!r}) — StatCan's profile "
            "table order changed; update CHARACTERISTIC_POPULATION."
        )
    if EXPECTED_NAME_INCOME not in seen_income_name:
        raise RuntimeError(
            f"CHARACTERISTIC_ID {CHARACTERISTIC_MEDIAN_HH_INCOME} no longer matches "
            f"'{EXPECTED_NAME_INCOME}' (got {seen_income_name!r}) — StatCan's profile "
            "table order changed; update CHARACTERISTIC_MEDIAN_HH_INCOME."
        )

    pop = profile[profile["CHARACTERISTIC_ID"] == CHARACTERISTIC_POPULATION][["DGUID", "C1_COUNT_TOTAL"]]
    pop = pop.rename(columns={"C1_COUNT_TOTAL": "population"})
    income = profile[profile["CHARACTERISTIC_ID"] == CHARACTERISTIC_MEDIAN_HH_INCOME][["DGUID", "C1_COUNT_TOTAL"]]
    income = income.rename(columns={"C1_COUNT_TOTAL": "median_household_income"})

    merged = pop.merge(income, on="DGUID", how="outer")
    merged["population"] = pd.to_numeric(merged["population"], errors="coerce")
    merged["median_household_income"] = pd.to_numeric(merged["median_household_income"], errors="coerce")
    merged = merged.rename(columns={"DGUID": "dguid"})
    return merged


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_census_tracts(boundaries: gpd.GeoDataFrame, profile: pd.DataFrame, chargers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    ct = boundaries.merge(profile, on="dguid", how="left")

    before = len(ct)
    ct = ct.dropna(subset=["population", "median_household_income"])
    ct = ct[ct["population"] > 0]
    dropped = before - len(ct)
    if dropped:
        print(f"[assemble] dropped {dropped} tracts with missing/suppressed population or income data")

    ct["income_percentile"] = ct["median_household_income"].rank(pct=True)

    # Assign each charger to its containing tract, then aggregate ports per tract.
    joined = gpd.sjoin(chargers, ct[["ct_uid", "geometry"]], how="left", predicate="within")
    chargers["ct_uid"] = joined["ct_uid"]

    # Only public stations count toward accessible supply — private/restricted
    # ones stay in the dataset (for the map) but shouldn't inflate the
    # per-tract supply ratio.
    public_chargers = chargers[chargers["access_code"] == "public"]
    port_totals = public_chargers.dropna(subset=["ct_uid"]).groupby("ct_uid")["total_ports"].sum()
    ct["port_count"] = ct["ct_uid"].map(port_totals).fillna(0).astype(int)

    ct["local_ratio"] = ct["port_count"] / ct["population"] * 1000
    citywide_avg_ratio = ct["port_count"].sum() / ct["population"].sum() * 1000
    ct["citywide_avg_ratio"] = citywide_avg_ratio

    print(
        f"[assemble] {len(ct):,} tracts, {int(ct['port_count'].sum()):,} ports assigned, "
        f"citywide avg {citywide_avg_ratio:.3f} ports/1,000 residents"
    )
    return ct, chargers


def save_geoparquet(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(path)
    print(f"[save] {path} ({path.stat().st_size / 1e6:.2f} MB, {len(gdf):,} rows)")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for built artifacts")
    args = parser.parse_args()

    work_dir = args.out / "_work"
    args.out.mkdir(parents=True, exist_ok=True)

    chargers = fetch_charging_stations()
    boundaries = fetch_census_tract_boundaries(TORONTO_BBOX)
    profile = fetch_census_profile(set(boundaries["dguid"]), work_dir)

    census_tracts, chargers = assemble_census_tracts(boundaries, profile, chargers)

    save_geoparquet(
        chargers[["address", "network", "level2_ports", "level3_ports", "total_ports", "access_code", "ct_uid", "geometry"]],
        args.out / "toronto_chargers.geoparquet",
    )
    save_geoparquet(
        census_tracts[[
            "ct_uid", "population", "median_household_income", "income_percentile",
            "port_count", "local_ratio", "citywide_avg_ratio", "geometry",
        ]],
        args.out / "toronto_census_tracts.geoparquet",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
