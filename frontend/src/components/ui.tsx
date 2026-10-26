import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-surface p-4 sm:p-5 ${className}`}>{children}</section>;
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-base font-semibold text-ink">{children}</h2>;
}

const TONES = {
  info: "bg-info-bg text-info-ink",
  warn: "bg-warn-bg text-warn-ink",
  bad: "bg-bad-bg text-bad-ink",
  good: "bg-good-bg text-good-ink",
};
const TONE_ICONS = { info: "ℹ", warn: "!", bad: "✕", good: "✓" };

/** A status message: tone is carried by an icon and text, not color alone. */
export function Notice({ tone = "info", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={`flex gap-2.5 rounded-lg px-3.5 py-3 text-sm ${TONES[tone]}`}>
      <span aria-hidden className="mt-px font-bold">{TONE_ICONS[tone]}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-surface-2 ${className}`} />;
}

export function Metric({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-0.5 text-xl font-semibold text-ink">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-2">{hint}</div>}
    </div>
  );
}

export function ExternalLink({ href, children, className = "" }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={`font-medium text-accent underline-offset-2 hover:underline ${className}`}>
      {children}
    </a>
  );
}

export function ButtonLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-2"
    >
      {children} <span aria-hidden>↗</span>
    </a>
  );
}

export function Disclosure({ summary, children, defaultOpen = false }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-line bg-surface">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">{summary}</span>
        <span aria-hidden className="text-ink-muted transition-transform group-open:rotate-90">›</span>
      </summary>
      <div className="border-t border-line px-4 py-3 text-sm text-ink-2">{children}</div>
    </details>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="mb-5">
      <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h1>
      <p className="mt-1 max-w-3xl text-ink-2">{subtitle}</p>
    </header>
  );
}

export function Legend({ items }: { items: { label: string; swatch: ReactNode }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-2">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-1.5">
          {it.swatch}
          {it.label}
        </li>
      ))}
    </ul>
  );
}

export const Dot = ({ color, ring = false }: { color: string; ring?: boolean }) => (
  <span
    aria-hidden
    className="inline-block h-3 w-3 shrink-0 rounded-full"
    style={{ background: color, boxShadow: ring ? "0 0 0 2px var(--surface), 0 0 0 3px var(--line)" : undefined }}
  />
);

export const AreaSwatch = ({ fill, line, dashed = false }: { fill: string; line: string; dashed?: boolean }) => (
  <span aria-hidden className="inline-block h-3 w-4 shrink-0 rounded-sm" style={{ background: fill, border: `1.5px ${dashed ? "dashed" : "solid"} ${line}` }} />
);
