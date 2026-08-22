#!/usr/bin/env python3
"""Build the census-tract-level EV charging supply/demand/income dataset.

Replaces per-address live API calls in supply_demand.py with a one-time
(periodic) bulk build. Run manually, or on a schedule via
.github/workflows/rebuild-ev-data.yml, which uploads the output artifacts as
GitHub Release assets for the app to download at startup (see data.py).

Three data sources, all fetched live by this script (no manual downloads):

1. Charging stations — City of Toronto Open Data, CKAN package
   "city-operated-electric-vehicle-charging-station-map". Resolved via
   package_show so we don't hardcode a resource ID that rotates on refresh.

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
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, shape

# Generous City of Toronto bounding box: (minx, miny, maxx, maxy) — mirrors
# geocode.py's TORONTO_BBOX.
TORONTO_BBOX = (-79.64, 43.58, -79.11, 43.86)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "build"

CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
CKAN_PACKAGE = "city-operated-electric-vehicle-charging-station-map"

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
# 1. Charging stations (City of Toronto Open Data)
# ---------------------------------------------------------------------------

def fetch_charging_stations() -> gpd.GeoDataFrame:
    print(f"[chargers] resolving CKAN package '{CKAN_PACKAGE}'")
    resp = requests.get(f"{CKAN_BASE}/api/3/action/package_show", params={"id": CKAN_PACKAGE}, timeout=60)
    resp.raise_for_status()
    package = resp.json()["result"]

    csv_resource = next(
        r for r in package["resources"]
        if r["format"].upper() == "CSV" and "4326" in r["name"]
    )
    print(f"[chargers] downloading {csv_resource['url']}")
    csv_text = requests.get(csv_resource["url"], timeout=120).content.decode("utf-8-sig")

    df = pd.read_csv(io.StringIO(csv_text))
    print(f"[chargers] {len(df):,} rows")

    def _lonlat(geom_json: str) -> tuple[float, float]:
        coords = json.loads(geom_json)["coordinates"]
        lon, lat = coords[0] if isinstance(coords[0], list) else coords
        return lon, lat

    lonlat = df["geometry"].apply(_lonlat)
    df["lon"] = lonlat.apply(lambda t: t[0])
    df["lat"] = lonlat.apply(lambda t: t[1])
    df["level2_ports"] = pd.to_numeric(df["Level2_Charging_Ports"], errors="coerce").fillna(0).astype(int)
    df["level3_ports"] = pd.to_numeric(df["Level3_Charging_Ports"], errors="coerce").fillna(0).astype(int)
    df["total_ports"] = df["level2_ports"] + df["level3_ports"]
    df["address"] = df["Address"]
    df["network"] = df["Type"]

    gdf = gpd.GeoDataFrame(
        df[["address", "network", "level2_ports", "level3_ports", "total_ports"]],
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
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
    port_totals = chargers.dropna(subset=["ct_uid"]).groupby("ct_uid")["total_ports"].sum()
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
        chargers[["address", "network", "level2_ports", "level3_ports", "total_ports", "ct_uid", "geometry"]],
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
