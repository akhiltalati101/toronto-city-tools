#!/usr/bin/env python3
"""Build city-wide walk/bike network graphs and amenity data from a local OSM extract.

Replaces the per-address Overpass calls in network.py / amenities.py with a
one-time (periodic) bulk build. Run manually, or on a schedule via
.github/workflows/rebuild-city-data.yml, which uploads the output artifacts
as GitHub Release assets for the app to download at startup (see citydata.py).

Requires the `osmium` CLI (https://osmcode.org/osmium-tool/) on PATH:
  brew install osmium-tool        # macOS
  apt-get install -y osmium-tool  # Debian/Ubuntu (used in CI)

Usage:
  python scripts/build_city_data.py             # full Toronto build
  python scripts/build_city_data.py --test       # small downtown bbox, fast local check
  python scripts/build_city_data.py --pbf FILE   # reuse an already-downloaded extract
"""
import argparse
import gc
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from amenities import CATEGORIES  # noqa: E402  (reuse the same tag definitions the app queries with)

BBBIKE_TORONTO_URL = "https://download.bbbike.org/osm/bbbike/Toronto/Toronto.osm.pbf"

# Generous City of Toronto bounding box: (minx, miny, maxx, maxy)
TORONTO_BBOX = (-79.64, 43.58, -79.11, 43.86)
# Small downtown-only bbox for fast local validation runs (--test)
TEST_BBOX = (-79.42, 43.64, -79.37, 43.67)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "build"

# Mirrors osmnx._overpass._get_network_filter's "walk"/"bike" Overpass QL
# filters, ported to a local tag check since we're filtering an offline
# extract instead of querying Overpass server-side. Verify against a live
# Overpass-sourced isochrone (see plan's verification step 2) before trusting
# this as authoritative.
NETWORK_TAG_RULES = {
    "walk": {
        "exclude_highway": {
            "abandoned", "bus_guideway", "construction", "cycleway", "no",
            "planned", "platform", "proposed", "raceway", "razed",
            "rest_area", "services",
        },
        "exclude_highway_prefix": ("motor",),
        "exclude": {"foot": {"no"}, "service": {"private"}, "access": {"private"}},
    },
    "bike": {
        "exclude_highway": {
            "abandoned", "bus_guideway", "construction", "corridor",
            "elevator", "escalator", "footway", "no", "planned", "platform",
            "proposed", "raceway", "razed", "rest_area", "services", "steps",
        },
        "exclude_highway_prefix": ("motor",),
        "exclude": {"bicycle": {"no"}, "service": {"private"}, "access": {"private"}},
    },
}


def _run(cmd: list[str]) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def download_extract(dest: Path, url: str = BBBIKE_TORONTO_URL) -> Path:
    if dest.exists():
        print(f"[skip] {dest} already downloaded")
        return dest
    print(f"[download] {url} -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    return dest


def clip_to_bbox(pbf_path: Path, bbox: tuple, out_pbf: Path) -> Path:
    bbox_str = ",".join(str(v) for v in bbox)
    _run(["osmium", "extract", "-b", bbox_str, str(pbf_path), "-o", str(out_pbf), "--overwrite"])
    return out_pbf


def filter_roads(pbf_path: Path, out_xml: Path) -> Path:
    """Keep only highway-tagged ways, converted to XML for ox.graph_from_xml.

    ox.graph_from_xml treats every way in the file as a road edge, so
    non-road ways/POIs must be filtered out first.
    """
    _run(["osmium", "tags-filter", str(pbf_path), "w/highway", "-o", str(out_xml), "--overwrite"])
    return out_xml


def _osmium_poi_filter_args(categories: dict) -> list[str]:
    """Build 'nwr/key=val1,val2,...' osmium tags-filter expressions from CATEGORIES.

    Merges value lists across categories that share a key (e.g. "amenity"
    appears in healthcare, schools, and transit) into one filter expression
    per key, keeping the filter's union semantics equivalent to querying each
    category's tags separately.
    """
    merged: dict[str, set] = {}
    for tags in categories.values():
        for key, values in tags.items():
            merged.setdefault(key, set()).update(values)
    return [f"nwr/{key}={','.join(sorted(vals))}" for key, vals in merged.items()]


def filter_pois(pbf_path: Path, out_xml: Path) -> Path:
    """Keep only nodes/ways matching one of our amenity categories' tags.

    Cuts a whole-city extract (which otherwise includes every building,
    landuse polygon, etc.) down to just what amenities.py's categories care
    about, before handing it to ox.features_from_xml — the unfiltered file is
    large enough to exhaust memory when parsed for a whole city.
    """
    filter_args = _osmium_poi_filter_args(CATEGORIES)
    _run(["osmium", "tags-filter", str(pbf_path), *filter_args, "-o", str(out_xml), "--overwrite"])
    return out_xml


def _highway_excluded(highway, rules: dict) -> bool:
    values = highway if isinstance(highway, list) else [highway]
    for v in values:
        v = str(v)
        if v in rules["exclude_highway"]:
            return True
        if any(v.startswith(p) for p in rules["exclude_highway_prefix"]):
            return True
    return False


def _tag_excluded(data: dict, rules: dict) -> bool:
    return any(str(data.get(key, "")) in bad_values for key, bad_values in rules["exclude"].items())


def build_network_graph(xml_path: Path, network_type: str) -> nx.MultiDiGraph:
    """Build one walk/bike graph for the whole extract area.

    Builds the full 'any highway' graph first (retain_all=True so filtering
    below isn't skewed by a premature largest-component truncation), trims
    edges that don't qualify for this network_type, then truncates to the
    largest connected component and simplifies — mirroring what
    ox.graph_from_point(network_type=...) does per-address today.
    """
    print(f"[graph] building '{network_type}' graph from {xml_path}")
    G = ox.graph_from_xml(
        str(xml_path), bidirectional=(network_type == "walk"), simplify=False, retain_all=True,
    )

    rules = NETWORK_TAG_RULES[network_type]
    drop_edges = [
        (u, v, k)
        for u, v, k, data in G.edges(keys=True, data=True)
        if _highway_excluded(data.get("highway"), rules) or _tag_excluded(data, rules)
    ]
    G.remove_edges_from(drop_edges)
    G.remove_nodes_from(list(nx.isolates(G)))

    G = ox.truncate.largest_component(G, strongly=False)
    G = ox.simplify_graph(G)
    print(f"    -> {len(G.nodes):,} nodes, {len(G.edges):,} edges")
    return G


def build_amenities(xml_path: Path) -> dict[str, gpd.GeoDataFrame]:
    """Bulk-extract every amenity category for the whole build area.

    Per-address filtering (.within(isochrone_polygon)) happens later, at
    request time, in amenities.py::query_amenities.
    """
    print("[amenities] extracting all categories from local extract")
    results = {}
    for category, tags in CATEGORIES.items():
        try:
            gdf = ox.features_from_xml(str(xml_path), tags=tags)
        except Exception:
            gdf = gpd.GeoDataFrame(geometry=[])

        if not gdf.empty:
            gdf = gdf.copy()
            utm = gdf.estimate_utm_crs()
            gdf["geometry"] = gdf.to_crs(utm).geometry.centroid
            gdf = gdf.set_crs(utm).to_crs("EPSG:4326")

        results[category] = gdf
        print(f"    {category:12s}: {len(gdf):,}")
    return results


def save_graph(G: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(G, f)
    print(f"[save] {path} ({path.stat().st_size / 1e6:.1f} MB)")


def save_amenities(amenities: dict[str, gpd.GeoDataFrame], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for category, gdf in amenities.items():
        if gdf.empty:
            continue
        frame = gdf[["geometry"]].copy()
        frame["category"] = category
        frame["name"] = gdf["name"] if "name" in gdf.columns else None
        frames.append(frame)

    combined = (
        gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
        if frames
        else gpd.GeoDataFrame(columns=["geometry", "category", "name"], crs="EPSG:4326")
    )
    combined.to_parquet(path)
    print(f"[save] {path} ({path.stat().st_size / 1e6:.1f} MB, {len(combined):,} rows)")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # so log tails show progress live, not just on exit

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test", action="store_true", help="Small downtown-only bbox, for a fast local validation run")
    parser.add_argument("--pbf", type=Path, help="Path to an already-downloaded .osm.pbf (skips download)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for built artifacts")
    args = parser.parse_args()

    bbox = TEST_BBOX if args.test else TORONTO_BBOX
    work_dir = args.out / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)

    pbf_path = args.pbf or download_extract(work_dir / "toronto_source.osm.pbf")
    clipped_pbf = clip_to_bbox(pbf_path, bbox, work_dir / "clipped.pbf")

    roads_xml = filter_roads(clipped_pbf, work_dir / "roads.osm")
    pois_xml = filter_pois(clipped_pbf, work_dir / "pois.osm")

    # Build, save, and free each artifact before starting the next — holding
    # all three in memory at once is what exhausted RAM on a whole-city build.
    # Skip any artifact that already exists, so a killed/crashed run can be
    # resumed without re-parsing everything from scratch.
    for network_type in ("walk", "bike"):
        out_path = args.out / f"toronto_{network_type}.graph.pkl"
        if out_path.exists():
            print(f"[skip] {out_path} already built")
            continue
        G = build_network_graph(roads_xml, network_type)
        save_graph(G, out_path)
        del G
        gc.collect()

    amenities_path = args.out / "toronto_amenities.geoparquet"
    if amenities_path.exists():
        print(f"[skip] {amenities_path} already built")
    else:
        amenities = build_amenities(pois_xml)
        save_amenities(amenities, amenities_path)
        del amenities
        gc.collect()

    print("\nDone.")


if __name__ == "__main__":
    main()
