import type { AreaScore, CityScore, EvScore, LocationQuery } from "./types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

/** An error with a message fit to show the user (the API's `detail`). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string, params: Record<string, string | number | undefined>): Promise<T> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") search.set(k, String(v));
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}?${search}`);
  } catch {
    throw new ApiError("Couldn't reach the scoring service. Check your connection and try again.", 0);
  }
  if (!resp.ok) {
    let detail = `Something went wrong (HTTP ${resp.status}).`;
    if (resp.status === 429) detail = "Too many requests — please wait a minute and try again.";
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // not JSON; keep the generic message
    }
    throw new ApiError(detail, resp.status);
  }
  return resp.json() as Promise<T>;
}

const locationParams = (q: LocationQuery) => ({ address: q.address, lat: q.lat, lon: q.lon });

export const fetchCityScore = (q: LocationQuery) => get<CityScore>("/api/city/score", locationParams(q));
export const fetchEvScore = (q: LocationQuery) => get<EvScore>("/api/ev/score", locationParams(q));
export const fetchAreaScore = (q: LocationQuery) => get<AreaScore>("/api/area/score", locationParams(q));
