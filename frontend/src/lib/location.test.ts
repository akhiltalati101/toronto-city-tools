import { describe, expect, it } from "vitest";
import { circlePolygon, locationKey, readLocation, writeLocation } from "./location";

describe("location URL params", () => {
  it("round-trips an address and a point", () => {
    const p = writeLocation(new URLSearchParams("tab=x"), { address: "100 Queen St W", lat: 43.65, lon: -79.38 });
    expect(p.get("tab")).toBe("x");
    expect(readLocation(p)).toEqual({ address: "100 Queen St W", lat: 43.65, lon: -79.38 });
  });

  it("keeps prefixed slots separate", () => {
    let p = writeLocation(new URLSearchParams(), { address: "A" }, "a_");
    p = writeLocation(p, { lat: 43.7, lon: -79.4 }, "b_");
    expect(readLocation(p, "a_")).toEqual({ address: "A" });
    expect(readLocation(p, "b_")).toEqual({ address: undefined, lat: 43.7, lon: -79.4 });
    expect(readLocation(p)).toBeNull();
  });

  it("clears a slot", () => {
    const p = writeLocation(new URLSearchParams("address=x&lat=1&lon=2"), null);
    expect(p.toString()).toBe("");
  });

  it("ignores case, spacing and commas in the cache key", () => {
    expect(locationKey({ address: "100 Queen St W, Toronto" })).toEqual(locationKey({ address: "100  queen st w toronto" }));
  });

  it("builds a closed circle", () => {
    const ring = circlePolygon(43.65, -79.38, 500).coordinates[0];
    expect(ring[0][0]).toBeCloseTo(ring[ring.length - 1][0], 12);
    expect(ring[0][1]).toBeCloseTo(ring[ring.length - 1][1], 12);
  });
});
