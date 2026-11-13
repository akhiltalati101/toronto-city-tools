import type { FeatureCollection, Point } from "geojson";
import { useEffect, useMemo, useState } from "react";
import { Layer, Popup, Source } from "react-map-gl/maplibre";
import { AddressSearch } from "../components/AddressSearch";
import { BaseMap } from "../components/BaseMap";
import { ErrorNotice, LoadingResults } from "../components/Loading";
import { ScoreCard } from "../components/ScoreCard";
import { AreaSwatch, Card, Disclosure, Dot, ExternalLink, Legend, Metric, Notice, PageHeader, SectionTitle } from "../components/ui";
import { useLocationQuery } from "../hooks/useLocationQuery";
import { fetchEvScore } from "../lib/api";
import { bounds } from "../lib/location";
import { CHARGER_COLORS, CONNECTOR_LABELS, ISOCHRONE_COLORS, NRCAN_COSTS_GUIDE_URL, NRCAN_INSTALL_GUIDE_URL } from "../lib/constants";
import { scoreFromWalkTimes } from "../lib/scoring";
import type { ChargerProps, EvScore, HomeCharging } from "../lib/types";

type ChargerState = keyof typeof CHARGER_COLORS;
type MapCharger = ChargerProps & { state: ChargerState; idx: number };

const STORAGE_KEY = "ev-connectors";

/** The connector selection is a per-viewer convenience, remembered locally when storage allows. */
function useConnectorSelection() {
  const [selected, setSelected] = useState<Set<string>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
      return new Set(Array.isArray(saved) ? saved.filter((c) => c in CONNECTOR_LABELS) : []);
    } catch {
      return new Set();
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...selected]));
    } catch {
      // storage unavailable (private mode etc.) — selection just isn't remembered
    }
  }, [selected]);
  const toggle = (code: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  return { selected, toggle };
}

export default function EvPage() {
  const { location, setLocation, query } = useLocationQuery("ev", fetchEvScore);
  const { selected, toggle } = useConnectorSelection();

  return (
    <div>
      <PageHeader
        title="Should I Own an EV?"
        subtitle="See how well a Toronto address is served by public EV charging you can actually plug into — plus whether it can likely support a home charger too."
      />
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="space-y-5">
          <AddressSearch initial={location?.address ?? ""} onSubmit={setLocation} busy={query.isFetching} />
          <Card>
            <SectionTitle>What does your car use?</SectionTitle>
            <p className="-mt-1 mb-3 text-xs text-ink-muted">
              Select every connector your car supports. Chargers you can't use are greyed out on the map and don't count toward your score.
            </p>
            <div className="space-y-2">
              {Object.entries(CONNECTOR_LABELS).map(([code, label]) => (
                <label key={code} className="flex cursor-pointer items-center gap-2.5 text-sm text-ink">
                  <input type="checkbox" checked={selected.has(code)} onChange={() => toggle(code)} className="h-4 w-4 accent-[var(--accent)]" />
                  {label}
                </label>
              ))}
            </div>
          </Card>
          {query.data && <EvSummary score={query.data} selected={selected} />}
          <HowItWorks />
        </div>
        <div className="min-w-0 space-y-4">
          {!location && <Notice>Enter a Toronto address to check its charging access.</Notice>}
          {query.isPending && location && <LoadingResults what="Checking this address" />}
          {query.isError && <ErrorNotice error={query.error} />}
          {query.data && (
            <>
              <h2 className="text-lg font-semibold text-ink">{query.data.address}</h2>
              <ChargerMap score={query.data} selected={selected} onPick={(lat, lon) => setLocation({ lat, lon })} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function chargerState(p: ChargerProps, selected: Set<string>): ChargerState {
  if (p.access_code !== "public") return "private";
  return p.connectors.some((c) => selected.has(c)) ? "compatible" : "incompatible";
}

function EvSummary({ score, selected }: { score: EvScore; selected: Set<string> }) {
  // Re-scored on every checkbox change, from walk times the API already sent.
  const access = useMemo(() => {
    const walkSecs = score.chargers.features
      .filter((f) => chargerState(f.properties, selected) === "compatible")
      .map((f) => f.properties.walk_sec);
    return scoreFromWalkTimes(walkSecs);
  }, [score, selected]);

  return (
    <div className="space-y-4">
      {selected.size === 0 ? (
        <Notice>Select your car's connector type(s) above to see your compatible charging score.</Notice>
      ) : (
        <>
          <ScoreCard score={access.combined} grade={access.grade} caption="compatible public charging access, out of 100" />
          <Card>
            <Metric
              label="Compatible charging availability"
              value={`${access.count} station${access.count === 1 ? "" : "s"}`}
              hint={
                <>
                  Within a 15-minute walk
                  {access.nearest_min !== null && <>, nearest {access.nearest_min} min away</>}. Only public stations whose connector matches your
                  selection count. {score.public_access.count} public stations of any type are in range.
                </>
              }
            />
          </Card>
        </>
      )}
      {score.home_charging.feasible && <HomeChargingPanel result={score.home_charging} />}
    </div>
  );
}

function HomeChargingPanel({ result }: { result: HomeCharging }) {
  return (
    <section className="rounded-xl bg-good-bg p-4 text-sm text-good-ink">
      <h3 className="font-semibold">✓ Home charging may also be available</h3>
      <p className="mt-1">
        Residence type: <strong>{result.dwelling_type}</strong> ({result.confidence} confidence). {result.note}
      </p>
      <p className="mt-2">
        Level 2 (240V) home charging is typically installable in a private driveway or garage, adding roughly 30–40 km of range per hour —
        enough for a full overnight charge. A licensed electrician can confirm your panel capacity and quote the install.
      </p>
      <p className="mt-2 text-xs">
        Natural Resources Canada: <ExternalLink href={NRCAN_INSTALL_GUIDE_URL}>how home charger installation works</ExternalLink> ·{" "}
        <ExternalLink href={NRCAN_COSTS_GUIDE_URL}>what it costs to charge at home</ExternalLink>. Some provinces and utilities offer their own
        install rebates — there's no federal one.
      </p>
    </section>
  );
}

function ChargerMap({ score, selected, onPick }: { score: EvScore; selected: Set<string>; onPick: (lat: number, lon: number) => void }) {
  const [popupIdx, setPopupIdx] = useState<number | null>(null);
  const data = useMemo<FeatureCollection<Point, MapCharger>>(
    () => ({
      type: "FeatureCollection",
      features: score.chargers.features.map((f, idx) => ({ ...f, properties: { ...f.properties, state: chargerState(f.properties, selected), idx } })),
    }),
    [score, selected],
  );
  const popup = popupIdx !== null ? data.features[popupIdx] : null;
  useEffect(() => setPopupIdx(null), [score]);
  const fit = useMemo(() => bounds([score.isochrone]), [score]);

  return (
    <div className="space-y-3">
      <BaseMap
        fit={fit}
        home={{ lat: score.lat, lon: score.lon, label: score.address }}
        interactiveLayerIds={["chargers"]}
        tooltip={(f) => {
          const p = f.properties as MapCharger;
          const ports = `${p.total_ports} port${p.total_ports === 1 ? "" : "s"}`;
          const note = p.state === "private" ? ` (access: ${p.access_code})` : p.state === "incompatible" ? " (not compatible with your connectors)" : "";
          return `${p.address ?? "Charging station"} — ${ports}${note}`;
        }}
        onFeatureClick={(f) => setPopupIdx(Number(f.properties.idx))}
        // With a popup open, a click on empty map just closes it.
        onPick={(lat, lon) => (popup ? setPopupIdx(null) : onPick(lat, lon))}
      >
        <Source id="ev-walk" type="geojson" data={score.isochrone}>
          <Layer id="ev-walk-fill" type="fill" paint={{ "fill-color": ISOCHRONE_COLORS.walk.fill, "fill-opacity": 0.3 }} />
          <Layer id="ev-walk-line" type="line" paint={{ "line-color": ISOCHRONE_COLORS.walk.line, "line-width": 2 }} />
        </Source>
        <Source id="ev-chargers" type="geojson" data={data}>
          <Layer
            id="chargers"
            type="circle"
            paint={{
              "circle-color": ["match", ["get", "state"], "compatible", CHARGER_COLORS.compatible, "private", CHARGER_COLORS.private, CHARGER_COLORS.incompatible],
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 4.5, 16, 8],
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 1.5,
            }}
            layout={{ "circle-sort-key": ["match", ["get", "state"], "compatible", 2, "private", 1, 0] }}
          />
        </Source>
        {popup && (
          <Popup
            latitude={popup.geometry.coordinates[1]}
            longitude={popup.geometry.coordinates[0]}
            onClose={() => setPopupIdx(null)}
            closeOnClick={false}
            maxWidth="300px"
          >
            <ChargerDetails p={popup.properties} />
          </Popup>
        )}
      </BaseMap>
      <Legend
        items={[
          { label: "Compatible public charger", swatch: <Dot color={CHARGER_COLORS.compatible} /> },
          { label: "Public, other connector", swatch: <Dot color={CHARGER_COLORS.incompatible} /> },
          { label: "Private / restricted", swatch: <Dot color={CHARGER_COLORS.private} /> },
          { label: "15-min walk", swatch: <AreaSwatch {...ISOCHRONE_COLORS.walk} /> },
        ]}
      />
    </div>
  );
}

function ChargerDetails({ p }: { p: ChargerProps }) {
  const rows: [string, string][] = [
    ["Connectors", p.connectors.length ? p.connectors.map((c) => CONNECTOR_LABELS[c] ?? c).join(", ") : "Not listed"],
    ["Level 2 / DC fast", `${p.level2_ports} / ${p.level3_ports} ports`],
    ["Pricing", p.pricing ?? "Not listed"],
    ["Hours", p.access_hours ?? "Not listed"],
    ["Walk", p.walk_sec !== null ? `${Math.round(p.walk_sec / 60)} min` : "—"],
  ];
  return (
    <div className="min-w-52 pr-4">
      <div className="font-semibold">{p.address ?? "Charging station"}</div>
      <div className="mb-2 text-ink-2">
        {p.network ?? "Unknown network"} · {p.access_code}
      </div>
      <table className="text-xs">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td className="whitespace-nowrap py-0.5 pr-3 align-top text-ink-muted">{k}</td>
              <td className="py-0.5">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HowItWorks() {
  return (
    <Disclosure summary="How this is calculated">
      <p>
        The headline score reflects <strong>compatible public charging access</strong>: how many publicly available stations your car can actually
        plug into are within a 15-minute walk (variety, 40%), and how close the nearest one is (proximity, 60%). Some networks — most Tesla
        Destination and Supercharger stations, for instance — only work with one connector, so counting every charger would overstate what you can
        use.
      </p>
      <p className="mt-2">
        It's a property of the location, not of who lives there — useful for top-ups, road trips or visitors even if you can charge at home. If the
        building looks like a detached, semi-detached or townhouse type that usually has a driveway, a panel notes that home charging may also be
        available.
      </p>
    </Disclosure>
  );
}
