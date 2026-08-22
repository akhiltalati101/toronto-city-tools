"""Scores a Toronto address on EV charging supply vs. demand, adjusted by
the local census tract's household income relative to the rest of the city.

Unlike city-scorecard's walkability score (one-directional: closer is always
better), this is two-directional — a census tract can have too little or too
much public charging supply relative to its population. See ev-scorecard's
README for the full methodology writeup and the modeling assumption this
formula makes explicit: lower-income tracts are held to a *higher* expected
supply bar, not a lower one, on the theory that scarce public charging is
itself a barrier to EV adoption in those areas rather than a sign of lower
need.
"""
from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
from shapely.geometry import Point

# Bucket thresholds for supply_index = local_ratio / income_adjusted_benchmark
BUCKETS = [
    (0.5, "Strongly Underserved", "#c62828"),
    (0.85, "Underserved", "#ef6c00"),
    (1.15, "Balanced", "#546e7a"),
    (1.5, "Overserved", "#1565c0"),
    (float("inf"), "Strongly Overserved", "#6a1b9a"),
]


@dataclass
class SupplyResult:
    ct_uid: str
    local_ratio: float             # ports per 1,000 residents in this tract
    citywide_avg_ratio: float      # ports per 1,000 residents, citywide average
    benchmark: float               # income-adjusted expected ratio for this tract
    supply_index: float            # local_ratio / benchmark
    label: str
    color: str
    income_percentile: float       # 0-1, this tract's median household income rank
    population: int
    port_count: int
    nearest_charger_m: Optional[float]


def _bucket(supply_index: float) -> tuple[str, str]:
    for threshold, label, color in BUCKETS:
        if supply_index < threshold:
            return label, color
    return BUCKETS[-1][1], BUCKETS[-1][2]


def locate_census_tract(lat: float, lon: float, ct_gdf: gpd.GeoDataFrame) -> gpd.GeoSeries:
    """Return the census tract row containing (lat, lon).

    Raises ValueError if the point doesn't fall inside any known tract
    (e.g. water, or just outside the built dataset's coverage).
    """
    point = Point(lon, lat)
    # "intersects" rather than strict "contains" — the boundary geometry is
    # generalized (see build_ev_data.py's maxAllowableOffset) for faster
    # fetches, so a point near a tract edge can otherwise land just outside
    # every polygon instead of inside exactly one.
    idx = ct_gdf.sindex.query(point, predicate="intersects")
    if len(idx) == 0:
        raise ValueError("Address does not fall within any known Toronto census tract.")
    return ct_gdf.iloc[idx[0]]


def _nearest_charger_distance_m(lat: float, lon: float, chargers_gdf: gpd.GeoDataFrame) -> Optional[float]:
    if chargers_gdf.empty:
        return None
    point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    utm = point.estimate_utm_crs()
    point_m = point.to_crs(utm).iloc[0]
    chargers_m = chargers_gdf.to_crs(utm)
    return float(chargers_m.distance(point_m).min())


def compute_supply_index(
    lat: float,
    lon: float,
    ct_gdf: gpd.GeoDataFrame,
    chargers_gdf: gpd.GeoDataFrame,
    k: float = 1.0,
) -> SupplyResult:
    """Compute the income-adjusted supply/demand index for the tract containing (lat, lon).

    k is the "equity weighting": 0 makes the benchmark income-blind (plain
    citywide average ratio); higher k pushes lower-income tracts' benchmark
    up (harder to look served) and higher-income tracts' benchmark down
    (easier to look served, or even overserved).
    """
    tract = locate_census_tract(lat, lon, ct_gdf)

    citywide_avg_ratio = float(tract["citywide_avg_ratio"])
    income_percentile = float(tract["income_percentile"])
    benchmark = citywide_avg_ratio * (1 + k * (0.5 - income_percentile))
    benchmark = max(benchmark, 1e-6)  # avoid divide-by-zero for degenerate k/percentile combos

    local_ratio = float(tract["local_ratio"])
    supply_index = round(local_ratio / benchmark, 2)
    label, color = _bucket(supply_index)

    ct_chargers = chargers_gdf[chargers_gdf["ct_uid"] == tract["ct_uid"]]
    nearest_m = _nearest_charger_distance_m(lat, lon, chargers_gdf)

    return SupplyResult(
        ct_uid=str(tract["ct_uid"]),
        local_ratio=round(local_ratio, 2),
        citywide_avg_ratio=round(citywide_avg_ratio, 2),
        benchmark=round(benchmark, 2),
        supply_index=supply_index,
        label=label,
        color=color,
        income_percentile=round(income_percentile, 3),
        population=int(tract["population"]),
        port_count=int(tract["port_count"]),
        nearest_charger_m=round(nearest_m, 0) if nearest_m is not None else None,
    )


if __name__ == "__main__":
    from data import get_census_tracts, get_charging_stations
    from geocode import geocode_address

    ct_gdf = get_census_tracts()
    chargers_gdf = get_charging_stations()

    for address in ("100 Queen St W", "25 Rathburn Rd W, Etobicoke"):
        print(f"\n=== {address} ===")
        lat, lon = geocode_address(address)
        result = compute_supply_index(lat, lon, ct_gdf, chargers_gdf, k=1.0)
        print(f"Tract {result.ct_uid}: {result.label} (index {result.supply_index})")
        print(
            f"  local {result.local_ratio}/1k vs benchmark {result.benchmark}/1k "
            f"(citywide avg {result.citywide_avg_ratio}/1k)"
        )
        print(f"  income percentile: {result.income_percentile:.2f}, population: {result.population}")
        nearest = f"{result.nearest_charger_m:.0f} m" if result.nearest_charger_m is not None else "—"
        print(f"  ports in tract: {result.port_count}, nearest charger: {nearest}")
