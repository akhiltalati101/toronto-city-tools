import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CATEGORY_LABELS } from "../lib/constants";
import { CATEGORIES, pyRound } from "../lib/scoring";
import type { CategoryScore } from "../lib/types";

const axis = { stroke: "var(--ink-muted)", fontSize: 12 };
const tooltipStyle = {
  contentStyle: { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)", fontSize: 13 },
  labelStyle: { color: "var(--ink)", fontWeight: 600 },
  itemStyle: { color: "var(--ink-2)" },
  cursor: { fill: "var(--surface-2)" },
};

/** Per-category combined score, one series: no legend needed, values labelled at the bar ends. */
export function CategoryChart({ breakdown }: { breakdown: Record<string, CategoryScore> }) {
  const data = CATEGORIES.map((c) => ({ label: CATEGORY_LABELS[c], score: breakdown[c].combined }));
  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 36, bottom: 4, left: 8 }} barCategoryGap={8}>
        <CartesianGrid horizontal={false} stroke="var(--line)" />
        <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={axis} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="label" width={86} tick={{ ...axis, fill: "var(--ink-2)" }} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <Tooltip {...tooltipStyle} formatter={(v) => [`${v} / 100`, "Score"]} />
        <Bar dataKey="score" fill="var(--accent)" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
          <LabelList dataKey="score" position="right" style={{ fill: "var(--ink-2)", fontSize: 12 }} formatter={(v) => pyRound(Number(v), 0)} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Categorical slots 1–2, stepped per theme in index.css.
export const COMPARE_COLORS = ["var(--series-1)", "var(--series-2)"];

export function CompareChart({ a, b }: { a: { label: string; breakdown: Record<string, CategoryScore> }; b: { label: string; breakdown: Record<string, CategoryScore> } }) {
  const data = CATEGORIES.map((c) => ({ label: CATEGORY_LABELS[c], a: a.breakdown[c].combined, b: b.breakdown[c].combined }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }} barGap={2} barCategoryGap="22%">
        <CartesianGrid vertical={false} stroke="var(--line)" />
        <XAxis dataKey="label" tick={{ ...axis, fill: "var(--ink-2)" }} axisLine={{ stroke: "var(--line)" }} tickLine={false} interval={0} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={axis} axisLine={false} tickLine={false} />
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 12 }} formatter={(value) => <span style={{ color: "var(--ink-2)" }}>{value}</span>} />
        <Bar dataKey="a" name={a.label} fill={COMPARE_COLORS[0]} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
        <Bar dataKey="b" name={b.label} fill={COMPARE_COLORS[1]} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
