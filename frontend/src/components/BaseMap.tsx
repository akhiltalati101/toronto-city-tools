import { setWorkerUrl, type MapGeoJSONFeature } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState, type ReactNode } from "react";
import Map, { Marker, NavigationControl, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import { MAP_STYLE } from "../lib/constants";

// MapLibre 6 loads its worker from a path relative to its own module, which
// doesn't exist once Vite pre-bundles (dev) or bundles (build) the library —
// the map then draws only the style background. Hand it Vite's URL instead.
setWorkerUrl(workerUrl);

const TORONTO = { latitude: 43.7, longitude: -79.39, zoom: 10 };

export type Bounds = [[number, number], [number, number]];

interface Props {
  /** Fit the view to these bounds whenever they change. */
  fit?: Bounds | null;
  home?: { lat: number; lon: number; label: string } | null;
  interactiveLayerIds?: string[];
  /** Hover text for a feature on one of interactiveLayerIds. */
  tooltip?: (f: MapGeoJSONFeature) => string | null;
  onFeatureClick?: (f: MapGeoJSONFeature) => void;
  /** Click on empty map: score this point instead. */
  onPick?: (lat: number, lon: number) => void;
  className?: string;
  overlay?: ReactNode;
  children?: ReactNode;
}

export function BaseMap({ fit, home, interactiveLayerIds, tooltip, onFeatureClick, onPick, className = "h-[420px] lg:h-[560px]", overlay, children }: Props) {
  const mapRef = useRef<MapRef>(null);
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);
  const fitKey = fit ? fit.flat().join(",") : "";

  useEffect(() => {
    if (fit && mapRef.current) mapRef.current.fitBounds(fit, { padding: 40, duration: 700, maxZoom: 16 });
    // fitKey captures fit's contents; re-fitting on identity changes would
    // fight the user's own panning on every re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  const onMove = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    const text = f && tooltip ? tooltip(f) : null;
    setHover(text ? { x: e.point.x, y: e.point.y, text } : null);
  };

  const onClick = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    if (f && onFeatureClick) onFeatureClick(f);
    else if (!f && onPick) onPick(e.lngLat.lat, e.lngLat.lng);
  };

  return (
    <div className={`relative overflow-hidden rounded-xl border border-line ${className}`}>
      <Map
        ref={mapRef}
        initialViewState={home ? { latitude: home.lat, longitude: home.lon, zoom: 14 } : TORONTO}
        onLoad={() => fit && mapRef.current?.fitBounds(fit, { padding: 40, duration: 0, maxZoom: 16 })}
        mapStyle={MAP_STYLE}
        interactiveLayerIds={interactiveLayerIds}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onClick={onClick}
        cursor={hover ? "pointer" : onPick ? "crosshair" : "grab"}
        attributionControl={{ compact: true }}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="top-right" showCompass={false} />
        {children}
        {home && (
          <Marker latitude={home.lat} longitude={home.lon} anchor="bottom">
            <HomePin label={home.label} />
          </Marker>
        )}
      </Map>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-64 rounded-md bg-ink px-2 py-1 text-xs text-page shadow"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          {hover.text}
        </div>
      )}
      {overlay}
      {onPick && (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-surface/90 px-2 py-1 text-xs text-ink-2 shadow-sm">
          Click anywhere on the map to score that spot
        </div>
      )}
    </div>
  );
}

function HomePin({ label }: { label: string }) {
  return (
    <svg width="30" height="38" viewBox="0 0 30 38" role="img" aria-label={label}>
      <title>{label}</title>
      <path d="M15 37C15 37 2 22 2 14a13 13 0 0 1 26 0c0 8-13 23-13 23z" fill="#0b0b0b" stroke="#fff" strokeWidth="2" />
      <path d="M9 15.5 15 10l6 5.5V21h-4v-3.5h-4V21H9z" fill="#fff" />
    </svg>
  );
}
