import type { LocationQuery } from "./types";

/**
 * The location being scored lives in the URL, so results are shareable and
 * the back button works: ?address=… and/or ?lat=…&lon=…, with a prefix for
 * the compare view's second slot (?b_address=…).
 */
export function readLocation(params: URLSearchParams, prefix = ""): LocationQuery | null {
  const address = params.get(`${prefix}address`)?.trim() || undefined;
  const lat = Number(params.get(`${prefix}lat`));
  const lon = Number(params.get(`${prefix}lon`));
  const hasPoint = params.has(`${prefix}lat`) && params.has(`${prefix}lon`) && Number.isFinite(lat) && Number.isFinite(lon);
  if (!address && !hasPoint) return null;
  return hasPoint ? { address, lat, lon } : { address };
}

export function writeLocation(params: URLSearchParams, q: LocationQuery | null, prefix = ""): URLSearchParams {
  const next = new URLSearchParams(params);
  for (const key of ["address", "lat", "lon"]) next.delete(`${prefix}${key}`);
  if (q?.address) next.set(`${prefix}address`, q.address);
  if (q?.lat !== undefined && q?.lon !== undefined) {
    next.set(`${prefix}lat`, q.lat.toFixed(6));
    next.set(`${prefix}lon`, q.lon.toFixed(6));
  }
  return next;
}

export const locationKey = (q: LocationQuery | null) =>
  q ? [q.address?.toLowerCase().replace(/[\s,]+/g, " ") ?? null, q.lat ?? null, q.lon ?? null] : [null];

/** A circle of `radiusM` metres as a GeoJSON polygon (equirectangular — fine at this scale). */
export function circlePolygon(lat: number, lon: number, radiusM: number, steps = 64): GeoJSON.Polygon {
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180));
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return { type: "Polygon", coordinates: [ring] };
}

export function bounds(polygons: GeoJSON.Polygon[]): [[number, number], [number, number]] | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of polygons)
    for (const [x, y] of p.coordinates[0]) {
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
    }
  return Number.isFinite(minX) ? [[minX, minY], [maxX, maxY]] : null;
}
