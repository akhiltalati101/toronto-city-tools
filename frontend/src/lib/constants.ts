import type { Category } from "./scoring";
import type { Grade, SafetyGrade } from "./types";

export const CATEGORY_LABELS: Record<Category, string> = {
  grocery: "Grocery",
  healthcare: "Healthcare",
  parks: "Parks",
  schools: "Schools",
  transit: "Transit",
  fitness: "Fitness",
};

// Categorical slots 1–6 in fixed order (validated for CVD separation; the
// lighter slots rely on the legend, layer toggles and tooltips for relief).
export const CATEGORY_COLORS: Record<Category, string> = {
  grocery: "#2a78d6",
  healthcare: "#eb6834",
  parks: "#1baf7a",
  schools: "#eda100",
  transit: "#e87ba4",
  fitness: "#008300",
};

// Always shown alongside the letter itself, never as color alone.
export const GRADE_COLORS: Record<Grade, string> = {
  A: "#2e7d32",
  B: "#66bb6a",
  C: "#fbc02d",
  D: "#fb8c00",
  F: "#e53935",
};

export const SAFETY_GRADE_COLORS: Record<SafetyGrade, string> = {
  "Safer than average": "#2e7d32",
  "About average": "#fbc02d",
  "Less safe than average": "#e53935",
};

export function rentSafeColor(score: number): string {
  if (score >= 80) return "#2e7d32";
  if (score >= 50) return "#fbc02d";
  return "#e53935";
}

// Codes match NREL's ev_connector_types (see toronto_tools/ev/charger_access.py).
export const CONNECTOR_LABELS: Record<string, string> = {
  J1772: "J1772 (standard Level 2)",
  J1772COMBO: "CCS / J1772 Combo (DC fast)",
  CHADEMO: "CHAdeMO (DC fast)",
  TESLA: "Tesla (NACS / J3400)",
};

export const ISOCHRONE_COLORS = {
  walk: { fill: "#a5d6a7", line: "#43a047" },
  bike: { fill: "#90caf9", line: "#1e88e5" },
};

export const CHARGER_COLORS = { compatible: "#2e7d32", incompatible: "#b0b0aa", private: "#fb8c00" };
export const ZONING_COLORS = { major: "#2a78d6", minor: "#898781" };

// Free vector basemap, no API key needed (https://openfreemap.org).
export const MAP_STYLE = import.meta.env.VITE_MAP_STYLE ?? "https://tiles.openfreemap.org/styles/positron";

// Natural Resources Canada guidance on home Level 2 charger installation.
// There's no federal home-charger rebate to link to (the federal EVAP program
// covers vehicle purchases, not charger installs).
export const NRCAN_INSTALL_GUIDE_URL =
  "https://natural-resources.canada.ca/energy-efficiency/transportation-energy-efficiency/electric-vehicles/electric-vehicle-charging-charger-installation";
export const NRCAN_COSTS_GUIDE_URL =
  "https://natural-resources.canada.ca/energy-efficiency/transportation-energy-efficiency/zero-emission-vehicles/electric-vehicle-charging-costs-ev-charging";
