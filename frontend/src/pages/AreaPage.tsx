import type { FeatureCollection, Point } from "geojson";
import { useEffect, useMemo, useState } from "react";
import { Layer, Popup, Source } from "react-map-gl/maplibre";
import { AddressSearch } from "../components/AddressSearch";
import { BaseMap } from "../components/BaseMap";
import { ErrorNotice, LoadingResults } from "../components/Loading";
import { ButtonLink, Card, Disclosure, Dot, ExternalLink, Legend, Notice, PageHeader, SectionTitle } from "../components/ui";
import { useLocationQuery } from "../hooks/useLocationQuery";
import { fetchAreaScore } from "../lib/api";
import { rentSafeColor, SAFETY_GRADE_COLORS, ZONING_COLORS } from "../lib/constants";
import { bounds, circlePolygon } from "../lib/location";
import type { AreaScore, Rental, Safety, ZoningApplication } from "../lib/types";

export default function AreaPage() {
  const { location, setLocation, query } = useLocationQuery("area", fetchAreaScore);
  const [focused, setFocused] = useState<number | null>(null);
  useEffect(() => setFocused(null), [query.data]);

  return (
    <div>
      <PageHeader
        title="Should I Live Here?"
        subtitle="Check a Toronto address for nearby zoning and development changes, a 6-month crime comparison, and (for rental buildings) official maintenance scores."
      />
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="space-y-5">
          <AddressSearch initial={location?.address ?? ""} onSubmit={setLocation} busy={query.isFetching} />
          {query.data && (
            <>
              <Card>
                <SectionTitle>Safety</SectionTitle>
                <SafetyCard safety={query.data.safety} />
              </Card>
              <Card>
                <SectionTitle>Rental building quality</SectionTitle>
                <RentalCard rental={query.data.rental} />
              </Card>
            </>
          )}
          <HowItWorks />
        </div>
        <div className="min-w-0 space-y-4">
          {!location && <Notice>Enter a Toronto address to see what's happening around it.</Notice>}
          {query.isPending && location && <LoadingResults what="Looking up this address" />}
          {query.isError && <ErrorNotice error={query.error} />}
          {query.data && (
            <>
              <h2 className="text-lg font-semibold text-ink">{query.data.address}</h2>
              <AreaMap score={query.data} focused={focused} setFocused={setFocused} onPick={(lat, lon) => setLocation({ lat, lon })} />
              <ZoningList score={query.data} onFocus={setFocused} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SafetyCard({ safety }: { safety: Safety }) {
  const color = SAFETY_GRADE_COLORS[safety.grade];
  const breakdown = Object.entries(safety.category_breakdown).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...breakdown.map(([, n]) => n));
  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-surface-2 px-4 py-4 text-center">
        <div className="flex items-center justify-center gap-2 text-lg font-bold text-ink">
          <Dot color={color} />
          {safety.grade}
        </div>
        <div className="text-xs text-ink-2">vs. citywide average, last {safety.window_days} days</div>
      </div>
      <div>
        <div className="text-sm text-ink-2">
          <span className="text-2xl font-semibold text-ink">{safety.local_incident_count}</span> incidents within {safety.radius_m} m
        </div>
        <p className="mt-1 text-xs text-ink-muted">
          Severity-weighted {safety.local_weighted_count} vs. {safety.expected_weighted_count} expected for an area this size at the citywide rate
          (ratio {safety.ratio}×). Weapons, robbery and break-ins weigh more than minor theft.
        </p>
      </div>
      {breakdown.length > 0 && (
        <ul className="space-y-1.5" aria-label="Incidents by category">
          {breakdown.map(([category, n]) => (
            <li key={category} className="grid grid-cols-[110px_1fr_auto] items-center gap-2 text-sm" title={`${category}: ${n}`}>
              <span className="truncate text-ink-2">{category}</span>
              <span className="h-2.5 rounded-r bg-[var(--accent)]" style={{ width: `${(n / max) * 100}%`, minWidth: 4 }} />
              <span className="tabular text-right text-ink">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RentalCard({ rental }: { rental: Rental }) {
  const { building, rentsafe, facebook_search_url } = rental;
  const fb = facebook_search_url && <ButtonLink href={facebook_search_url}>Search Facebook groups for this building</ButtonLink>;

  if (building.status === "not_apartment") return <Notice>{building.note}</Notice>;
  if (building.status === "unknown")
    return (
      <div className="space-y-3">
        <Notice>
          {building.note} It isn't registered with RentSafeTO either, so it's likely not a rental apartment building — it may be a house, a small
          rental, or an owner-occupied condo, which RentSafeTO doesn't cover.
        </Notice>
        {fb}
      </div>
    );
  if (!rentsafe)
    return (
      <div className="space-y-3">
        <Notice tone="warn">
          This looks like an apartment/condo building, but it's not registered with RentSafeTO. That program only covers rental apartment buildings —
          not owner-occupied condo corporations — so this is likely a condo, not a missing data point.
        </Notice>
        {fb}
      </div>
    );

  const score = rentsafe.overall_score;
  return (
    <div className="space-y-3">
      <div className="rounded-lg bg-surface-2 px-4 py-4 text-center">
        <div className="flex items-center justify-center gap-2 text-4xl font-extrabold text-ink">
          {score !== null && <Dot color={rentSafeColor(score)} />}
          {score ?? "—"}
        </div>
        <div className="text-xs text-ink-2">RentSafeTO building score, out of 100</div>
      </div>
      <p className="text-xs text-ink-muted">
        {rentsafe.address} · {rentsafe.storeys ?? "?"} storeys, {rentsafe.units ?? "?"} units · evaluated {rentsafe.evaluated_on ?? "n/a"} (
        {rentsafe.property_type ?? "unknown type"})
      </p>
      {rentsafe.lowest_categories.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium text-ink-2">Lowest-scoring inspection categories (1 = worst, 3 = best)</div>
          <ul className="space-y-1 text-sm">
            {rentsafe.lowest_categories.map((c) => (
              <li key={c.category} className="flex justify-between">
                <span className="text-ink">{c.category}</span>
                <span className="tabular font-medium text-ink">{c.score}/3</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function AreaMap({ score, focused, setFocused, onPick }: { score: AreaScore; focused: number | null; setFocused: (i: number | null) => void; onPick: (lat: number, lon: number) => void }) {
  const circle = useMemo(() => circlePolygon(score.lat, score.lon, score.safety.radius_m), [score]);
  const zoning = useMemo<FeatureCollection<Point, { idx: number; major: boolean; label: string }>>(
    () => ({
      type: "FeatureCollection",
      features: score.zoning.map((z, idx) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [z.lon, z.lat] },
        properties: { idx, major: z.is_major, label: `${z.folder_type} — ${z.address}` },
      })),
    }),
    [score],
  );
  const fit = useMemo(() => bounds([circle, circlePolygon(score.lat, score.lon, score.zoning_radius_m)]), [circle, score]);
  const color = SAFETY_GRADE_COLORS[score.safety.grade];
  const popup = focused !== null ? score.zoning[focused] : null;

  return (
    <div className="space-y-3">
      <BaseMap
        fit={fit}
        home={{ lat: score.lat, lon: score.lon, label: score.address }}
        interactiveLayerIds={["zoning"]}
        tooltip={(f) => String(f.properties.label)}
        onFeatureClick={(f) => setFocused(Number(f.properties.idx))}
        onPick={(lat, lon) => (popup ? setFocused(null) : onPick(lat, lon))}
        overlay={
          <div className="pointer-events-none absolute left-2 top-2 rounded-lg bg-surface/95 px-3 py-2 text-center shadow">
            <div className="flex items-center gap-1.5 text-sm font-bold text-ink">
              <Dot color={color} /> {score.safety.grade}
            </div>
            <div className="text-xs text-ink-2">vs. citywide (6 mo)</div>
          </div>
        }
      >
        <Source id="area-safety" type="geojson" data={circle}>
          <Layer id="area-safety-fill" type="fill" paint={{ "fill-color": color, "fill-opacity": 0.08 }} />
          <Layer id="area-safety-line" type="line" paint={{ "line-color": color, "line-width": 2 }} />
        </Source>
        <Source id="area-zoning" type="geojson" data={zoning}>
          <Layer
            id="zoning"
            type="circle"
            paint={{
              "circle-color": ["case", ["get", "major"], ZONING_COLORS.major, ZONING_COLORS.minor],
              "circle-radius": ["case", ["get", "major"], 8, 6],
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 2,
            }}
          />
        </Source>
        {popup && (
          <Popup latitude={popup.lat} longitude={popup.lon} onClose={() => setFocused(null)} closeOnClick={false} maxWidth="300px">
            <ZoningPopup z={popup} />
          </Popup>
        )}
      </BaseMap>
      <Legend
        items={[
          { label: "Major application (planning / TLAB)", swatch: <Dot color={ZONING_COLORS.major} /> },
          { label: "Minor (e.g. minor variance)", swatch: <Dot color={ZONING_COLORS.minor} /> },
          { label: `${score.safety.radius_m} m safety catchment`, swatch: <span aria-hidden className="inline-block h-3 w-3 rounded-full border-2" style={{ borderColor: color }} /> },
        ]}
      />
    </div>
  );
}

function ZoningPopup({ z }: { z: ZoningApplication }) {
  return (
    <div className="max-w-64 pr-4">
      <div className="font-semibold">{z.address || "Unknown address"}</div>
      <div className="mb-1.5 text-ink-2">
        {z.folder_type} · {z.status}
      </div>
      <div>{z.display_text}</div>
      {z.aic_url && (
        <div className="mt-2">
          <ExternalLink href={z.aic_url}>View official application →</ExternalLink>
        </div>
      )}
    </div>
  );
}

const formatDate = (ms: number | null) => (ms ? new Date(ms).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" }) : null);

function ZoningList({ score, onFocus }: { score: AreaScore; onFocus: (i: number) => void }) {
  return (
    <Card>
      <SectionTitle>Zoning & development applications nearby</SectionTitle>
      {score.zoning.length === 0 ? (
        <Notice>No active zoning or development applications found within {score.zoning_radius_m} m of this address.</Notice>
      ) : (
        <ul className="space-y-2">
          {score.zoning.map((z, i) => (
            <li key={z.application_number || i}>
              <Disclosure
                summary={
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <Dot color={z.is_major ? ZONING_COLORS.major : ZONING_COLORS.minor} />
                    {z.is_major && <span className="rounded bg-info-bg px-1.5 text-xs font-semibold text-info-ink">Major</span>}
                    <span className="text-ink">{z.address || "Unknown address"}</span>
                    <span className="text-xs font-normal text-ink-muted">
                      {z.folder_type} · {z.status}
                    </span>
                  </span>
                }
              >
                <p className="text-ink">{z.display_text}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
                  {formatDate(z.intake_date_ms) && <span>Submitted {formatDate(z.intake_date_ms)}</span>}
                  {formatDate(z.hearing_date_ms) && <span>Hearing {formatDate(z.hearing_date_ms)}</span>}
                  <button type="button" onClick={() => onFocus(i)} className="font-medium text-accent hover:underline">
                    Show on map
                  </button>
                  {z.aic_url && <ExternalLink href={z.aic_url}>View official application ↗</ExternalLink>}
                </div>
              </Disclosure>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function HowItWorks() {
  return (
    <Disclosure summary="How this is calculated">
      <ul className="list-disc space-y-2 pl-4">
        <li>
          <strong>Zoning & development</strong> — live lookup against the City of Toronto's Application Information Centre for active applications
          within 400 m. Descriptions are summarized in plain English where possible, otherwise shown as the city's own text.
        </li>
        <li>
          <strong>Safety</strong> — Toronto Police Community Safety Indicators for the last 6 months within 500 m, weighted by severity and compared
          to what you'd expect for an area that size at the citywide rate. Incident locations are offset to the nearest intersection for privacy, so
          treat this as directional.
        </li>
        <li>
          <strong>Rental building quality</strong> — for a registered rental apartment building, its official RentSafeTO evaluation score.
          RentSafeTO doesn't cover owner-occupied condo corporations, so an unregistered apartment building is most likely a condo.
        </li>
      </ul>
    </Disclosure>
  );
}
