import { useState } from "react";
import { useSearchParams } from "react-router";
import { AddressSearch } from "../components/AddressSearch";
import { CategoryChart, COMPARE_COLORS, CompareChart } from "../components/CityCharts";
import { CityMap } from "../components/CityMap";
import { ErrorNotice, LoadingResults } from "../components/Loading";
import { GradeChip, ScoreCard } from "../components/ScoreCard";
import { Card, Disclosure, Notice, PageHeader, SectionTitle } from "../components/ui";
import { useLocationQuery } from "../hooks/useLocationQuery";
import { fetchCityScore } from "../lib/api";
import { CATEGORY_LABELS } from "../lib/constants";
import { applyWeights, CATEGORIES, fromPercents, percentTotal, PROFILES, pyRound, toPercents, type Weights } from "../lib/scoring";
import type { CityScore } from "../lib/types";

export default function CityPage() {
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") === "compare" ? "compare" : "single";
  const weights = useWeights();

  const setMode = (m: "single" | "compare") =>
    setParams((p) => {
      const next = new URLSearchParams(p);
      if (m === "compare") next.set("mode", "compare");
      else next.delete("mode");
      return next;
    });

  return (
    <div>
      <PageHeader title="City Scorecard" subtitle="Score any Toronto address on the 15-minute city standard." />
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="order-2 lg:order-1 lg:sticky lg:top-4 lg:self-start">
          <WeightsPanel {...weights} />
        </aside>
        <div className="order-1 min-w-0 lg:order-2">
          <div role="tablist" aria-label="Mode" className="mb-4 inline-flex rounded-lg border border-line bg-surface p-1 text-sm">
            {(["single", "compare"] as const).map((m) => (
              <button
                key={m}
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={`rounded-md px-3 py-1.5 font-medium ${mode === m ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink"}`}
              >
                {m === "single" ? "Score an address" : "Compare addresses"}
              </button>
            ))}
          </div>
          {mode === "single" ? <SingleView weights={weights.active} /> : <CompareView weights={weights.active} />}
        </div>
      </div>
    </div>
  );
}

/**
 * Slider state, as whole percents. Scores re-weight instantly from the
 * breakdown already fetched; while the sliders don't total 100%, the last
 * valid set stays in use.
 */
function useWeights() {
  const [profile, setProfile] = useState("General");
  const [percents, setPercents] = useState<Weights>(() => toPercents(PROFILES.General));
  const [active, setActive] = useState<Weights>(PROFILES.General);

  const update = (next: Weights) => {
    setPercents(next);
    if (percentTotal(next) === 100) setActive(fromPercents(next));
  };
  const applyProfile = (name: string) => {
    setProfile(name);
    setPercents(toPercents(PROFILES[name]));
    setActive(PROFILES[name]);
  };
  return { profile, percents, active, update, applyProfile };
}

function WeightsPanel({ profile, percents, update, applyProfile }: ReturnType<typeof useWeights>) {
  const total = percentTotal(percents);
  const diff = 100 - total;
  return (
    <Card>
      <SectionTitle>Profile</SectionTitle>
      <div className="flex gap-2">
        <select
          aria-label="Preset profile"
          value={profile}
          onChange={(e) => applyProfile(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 py-2 text-sm text-ink"
        >
          {Object.keys(PROFILES).map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => applyProfile(profile)}
          className="rounded-lg border border-line px-3 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink"
        >
          Reset
        </button>
      </div>

      <h3 className="mb-1 mt-5 text-sm font-semibold text-ink">Fine-tune weights</h3>
      <p className="mb-3 text-xs text-ink-muted">Each category's share of the overall score. Must total 100%.</p>
      <div className="space-y-3">
        {CATEGORIES.map((c) => (
          <div key={c}>
            <div className="flex items-baseline justify-between text-sm">
              <label htmlFor={`w-${c}`} className="text-ink-2">
                {CATEGORY_LABELS[c]}
              </label>
              <span className="tabular font-medium text-ink">{percents[c]}%</span>
            </div>
            <input
              id={`w-${c}`}
              type="range"
              min={0}
              max={100}
              step={5}
              value={percents[c]}
              onChange={(e) => update({ ...percents, [c]: Number(e.target.value) })}
              className="w-full accent-[var(--accent)]"
            />
          </div>
        ))}
      </div>
      <div className="mt-3">
        {total === 100 ? (
          <Notice tone="good">Total: 100%</Notice>
        ) : (
          <Notice tone="bad">
            Total: {total}% — {diff > 0 ? "add" : "remove"} {Math.abs(diff)}% to reach 100%. Scores use the last valid weights until then.
          </Notice>
        )}
      </div>
    </Card>
  );
}

function SingleView({ weights }: { weights: Weights }) {
  const { location, setLocation, query } = useLocationQuery("city", fetchCityScore);
  return (
    <div className="space-y-5">
      <AddressSearch initial={location?.address ?? ""} onSubmit={setLocation} submitLabel="Score it" busy={query.isFetching} />
      {!location && <Notice>Enter a Toronto address, or pick a suggestion, to see its score.</Notice>}
      {query.isPending && location && <LoadingResults />}
      {query.isError && <ErrorNotice error={query.error} />}
      {query.data && <CityResult score={query.data} weights={weights} onPick={(lat, lon) => setLocation({ lat, lon })} />}
    </div>
  );
}

function CityResult({ score, weights, onPick }: { score: CityScore; weights: Weights; onPick: (lat: number, lon: number) => void }) {
  const result = applyWeights(score.breakdown, weights);
  const weak = CATEGORIES.filter((c) => score.breakdown[c].combined < 50);
  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-ink">{score.address}</h2>
      <div className="grid gap-4 md:grid-cols-[240px_1fr]">
        <ScoreCard score={result.overall} grade={result.grade} caption="out of 100" className="h-full" />
        <Card>
          <SectionTitle>Category breakdown</SectionTitle>
          <CategoryChart breakdown={score.breakdown} />
        </Card>
      </div>
      {weak.length > 0 && (
        <Notice tone="warn">
          Below-average access: <strong>{weak.map((c) => CATEGORY_LABELS[c]).join(", ")}</strong>
        </Notice>
      )}
      <CityMap score={score} onPick={onPick} />
      <Disclosure summary="Category details">
        <CategoryTable score={score} />
      </Disclosure>
      <HowItWorks />
    </div>
  );
}

function CategoryTable({ score }: { score: CityScore }) {
  return (
    <div className="overflow-x-auto">
      <table className="tabular w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-ink-muted">
          <tr>
            <th className="py-1.5 pr-3 font-medium">Category</th>
            <th className="py-1.5 pr-3 text-right font-medium">Score</th>
            <th className="py-1.5 pr-3 text-right font-medium">Proximity</th>
            <th className="py-1.5 pr-3 text-right font-medium">Variety</th>
            <th className="py-1.5 pr-3 text-right font-medium">Count</th>
            <th className="py-1.5 text-right font-medium">Nearest</th>
          </tr>
        </thead>
        <tbody className="text-ink">
          {CATEGORIES.map((c) => {
            const s = score.breakdown[c];
            return (
              <tr key={c} className="border-t border-line">
                <td className="py-1.5 pr-3">{CATEGORY_LABELS[c]}</td>
                <td className="py-1.5 pr-3 text-right font-semibold">{s.combined}</td>
                <td className="py-1.5 pr-3 text-right">{s.proximity}</td>
                <td className="py-1.5 pr-3 text-right">{s.variety}</td>
                <td className="py-1.5 pr-3 text-right">{s.count}</td>
                <td className="py-1.5 text-right">{s.nearest_min !== null ? `${s.nearest_min} min` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function HowItWorks() {
  return (
    <Disclosure summary="How this is calculated">
      <p>
        Each category is scored on <strong>proximity</strong> (60%) — the walk time along real streets to the nearest
        amenity, full marks within 5 minutes, zero at 15 — and <strong>variety</strong> (40%) — how many are within a
        15-minute walk, against a per-category target. The overall score is the weighted average of the six
        categories, using your profile's weights. The dashed outline shows how far a 15-minute bike ride reaches.
      </p>
    </Disclosure>
  );
}

function CompareView({ weights }: { weights: Weights }) {
  const a = useLocationQuery("city", fetchCityScore, "a_");
  const b = useLocationQuery("city", fetchCityScore, "b_");
  const ra = a.query.data ? applyWeights(a.query.data.breakdown, weights) : null;
  const rb = b.query.data ? applyWeights(b.query.data.breakdown, weights) : null;
  const slots = [
    { s: a, r: ra, color: COMPARE_COLORS[0], label: "Address A", placeholder: "e.g. 100 Queen St W", id: "a" },
    { s: b, r: rb, color: COMPARE_COLORS[1], label: "Address B", placeholder: "e.g. 25 Rathburn Rd W, Etobicoke", id: "b" },
  ];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        {slots.map(({ s, label, placeholder, id }) => (
          <AddressSearch key={id} label={label} placeholder={placeholder} initial={s.location?.address ?? ""} onSubmit={s.setLocation} submitLabel="Score" busy={s.query.isFetching} />
        ))}
      </div>

      {a.query.data && b.query.data && ra && rb && (
        <Notice tone="info">
          {ra.overall === rb.overall ? (
            <>Tied at {pyRound(ra.overall, 0)}</>
          ) : (
            <>
              <strong>{ra.overall > rb.overall ? a.query.data.address : b.query.data.address}</strong> scores higher (
              {pyRound(Math.max(ra.overall, rb.overall), 0)} vs {pyRound(Math.min(ra.overall, rb.overall), 0)})
            </>
          )}
        </Notice>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {slots.map(({ s, r, color, id }) => (
          <div key={id} className="min-w-0 space-y-3">
            {!s.location && <Notice>Enter an address to compare.</Notice>}
            {s.query.isPending && s.location && <LoadingResults />}
            {s.query.isError && <ErrorNotice error={s.query.error} />}
            {s.query.data && r && (
              <>
                <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                  <span aria-hidden className="h-3 w-3 rounded-sm" style={{ background: color }} />
                  {s.query.data.address}
                  <GradeChip grade={r.grade} />
                </h2>
                <ScoreCard score={r.overall} grade={r.grade} caption="out of 100" />
              </>
            )}
          </div>
        ))}
      </div>

      {a.query.data && b.query.data && (
        <Card>
          <SectionTitle>Category breakdown</SectionTitle>
          <CompareChart a={{ label: a.query.data.address, breakdown: a.query.data.breakdown }} b={{ label: b.query.data.address, breakdown: b.query.data.breakdown }} />
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        {slots.map(({ s, id }) =>
          s.query.data ? (
            <div key={id} className="min-w-0 space-y-3">
              <CityMap score={s.query.data} idPrefix={`city-${id}`} onPick={(lat, lon) => s.setLocation({ lat, lon })} className="h-[380px]" />
              <Disclosure summary={`Category details — ${s.query.data.address}`}>
                <CategoryTable score={s.query.data} />
              </Disclosure>
            </div>
          ) : null,
        )}
      </div>
    </div>
  );
}
