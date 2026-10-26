import type { ExpressionSpecification } from "maplibre-gl";
import { useMemo, useState } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import { CATEGORY_COLORS, CATEGORY_LABELS, ISOCHRONE_COLORS } from "../lib/constants";
import { bounds } from "../lib/location";
import { CATEGORIES, type Category } from "../lib/scoring";
import type { CityScore } from "../lib/types";
import { BaseMap } from "./BaseMap";
import { AreaSwatch, Legend } from "./ui";

const colorByCategory = [
  "match",
  ["get", "category"],
  ...CATEGORIES.flatMap((c) => [c, CATEGORY_COLORS[c]]),
  "#898781",
] as unknown as ExpressionSpecification;

/** Walk/bike isochrones plus amenity points, with per-category layer toggles. */
export function CityMap({ score, onPick, idPrefix = "city", className }: { score: CityScore; onPick?: (lat: number, lon: number) => void; idPrefix?: string; className?: string }) {
  const [visible, setVisible] = useState<Set<Category>>(() => new Set(CATEGORIES));
  const [showBike, setShowBike] = useState(true);
  const counts = useMemo(() => {
    const c = Object.fromEntries(CATEGORIES.map((k) => [k, 0])) as Record<Category, number>;
    for (const f of score.amenities.features) c[f.properties.category as Category] += 1;
    return c;
  }, [score]);
  // Framed on the walk range, which holds every scored amenity; the bike
  // range runs off the edges at this zoom.
  const fit = useMemo(() => bounds([score.walk_isochrone]), [score]);

  const toggle = (c: Category) =>
    setVisible((v) => {
      const next = new Set(v);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });

  const amenitiesLayer = `${idPrefix}-amenities`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Amenity layers">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={visible.has(c)}
            onClick={() => toggle(c)}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition ${
              visible.has(c) ? "border-line bg-surface text-ink" : "border-dashed border-line bg-transparent text-ink-muted line-through"
            }`}
          >
            <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_COLORS[c], opacity: visible.has(c) ? 1 : 0.35 }} />
            {CATEGORY_LABELS[c]} <span className="tabular text-ink-muted">{counts[c]}</span>
          </button>
        ))}
        <button
          type="button"
          aria-pressed={showBike}
          onClick={() => setShowBike((s) => !s)}
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${showBike ? "border-line bg-surface text-ink" : "border-dashed border-line text-ink-muted line-through"}`}
        >
          <AreaSwatch {...ISOCHRONE_COLORS.bike} dashed /> Bike range
        </button>
      </div>
      <BaseMap
        fit={fit}
        home={{ lat: score.lat, lon: score.lon, label: score.address }}
        interactiveLayerIds={[amenitiesLayer]}
        tooltip={(f) => {
          const cat = CATEGORY_LABELS[f.properties.category as Category];
          return f.properties.name ? `${f.properties.name} · ${cat}` : cat;
        }}
        onPick={onPick}
        className={className}
      >
        {showBike && (
          <Source id={`${idPrefix}-bike`} type="geojson" data={score.bike_isochrone}>
            <Layer id={`${idPrefix}-bike-fill`} type="fill" paint={{ "fill-color": ISOCHRONE_COLORS.bike.fill, "fill-opacity": 0.14 }} />
            <Layer id={`${idPrefix}-bike-line`} type="line" paint={{ "line-color": ISOCHRONE_COLORS.bike.line, "line-width": 2, "line-dasharray": [3, 3] }} />
          </Source>
        )}
        <Source id={`${idPrefix}-walk`} type="geojson" data={score.walk_isochrone}>
          <Layer id={`${idPrefix}-walk-fill`} type="fill" paint={{ "fill-color": ISOCHRONE_COLORS.walk.fill, "fill-opacity": 0.3 }} />
          <Layer id={`${idPrefix}-walk-line`} type="line" paint={{ "line-color": ISOCHRONE_COLORS.walk.line, "line-width": 2 }} />
        </Source>
        <Source id={`${idPrefix}-amenities-src`} type="geojson" data={score.amenities}>
          <Layer
            id={amenitiesLayer}
            type="circle"
            filter={["in", ["get", "category"], ["literal", [...visible]]]}
            paint={{
              "circle-color": colorByCategory,
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 3.5, 16, 7],
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 1.5,
            }}
          />
        </Source>
      </BaseMap>
      <Legend
        items={[
          { label: "15-min walk", swatch: <AreaSwatch {...ISOCHRONE_COLORS.walk} /> },
          { label: "15-min bike", swatch: <AreaSwatch {...ISOCHRONE_COLORS.bike} dashed /> },
        ]}
      />
    </div>
  );
}
