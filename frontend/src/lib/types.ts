// Mirrors api/schemas.py.
import type { FeatureCollection, Point, Polygon } from "geojson";

export type Grade = "A" | "B" | "C" | "D" | "F";

export interface Location {
  address: string;
  lat: number;
  lon: number;
}

export interface CategoryScore {
  proximity: number;
  variety: number;
  combined: number;
  count: number;
  nearest_min: number | null;
}

export interface CityScore extends Location {
  overall: number;
  grade: Grade;
  weights: Record<string, number>;
  breakdown: Record<string, CategoryScore>;
  walk_isochrone: Polygon;
  bike_isochrone: Polygon;
  amenities: FeatureCollection<Point, { category: string; name: string | null }>;
}

export interface HomeCharging {
  feasible: boolean;
  confidence: "high" | "medium" | "low";
  dwelling_type: string;
  note: string;
}

export interface ChargerAccess {
  combined: number;
  proximity: number;
  variety: number;
  count: number;
  nearest_min: number | null;
  grade: Grade;
}

export interface ChargerProps {
  address: string | null;
  network: string | null;
  access_code: string;
  connectors: string[];
  level2_ports: number;
  level3_ports: number;
  total_ports: number;
  pricing: string | null;
  access_hours: string | null;
  walk_sec: number | null;
}

export interface EvScore extends Location {
  home_charging: HomeCharging;
  public_access: ChargerAccess;
  isochrone: Polygon;
  chargers: FeatureCollection<Point, ChargerProps>;
}

export type SafetyGrade = "Safer than average" | "About average" | "Less safe than average";

export interface Safety {
  local_incident_count: number;
  local_weighted_count: number;
  citywide_weighted_count: number;
  expected_weighted_count: number;
  ratio: number;
  grade: SafetyGrade;
  category_breakdown: Record<string, number>;
  radius_m: number;
  window_days: number;
}

export interface RentSafe {
  address: string;
  overall_score: number | null;
  evaluated_on: string | null;
  storeys: number | null;
  units: number | null;
  property_type: string | null;
  lowest_categories: { category: string; score: number }[];
}

export interface Rental {
  building: { status: "apartment" | "not_apartment" | "unknown"; dwelling_type: string; note: string };
  rentsafe: RentSafe | null;
  facebook_search_url: string | null;
}

export interface ZoningApplication {
  application_number: string;
  address: string;
  application_type: string;
  folder_type: string;
  status: string;
  description: string | null;
  summary: string | null;
  display_text: string;
  intake_date_ms: number | null;
  hearing_date_ms: number | null;
  aic_url: string | null;
  lat: number;
  lon: number;
  is_major: boolean;
}

export interface AreaScore extends Location {
  safety: Safety;
  rental: Rental;
  zoning: ZoningApplication[];
  zoning_radius_m: number;
}

/** What the user asked to score: an address, a map point, or both. */
export interface LocationQuery {
  address?: string;
  lat?: number;
  lon?: number;
}
