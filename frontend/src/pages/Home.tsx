import { Link } from "react-router";

const TOOLS = [
  {
    to: "/city",
    title: "City Scorecard",
    blurb:
      "Score any Toronto address on the 15-minute city standard: groceries, healthcare, parks, schools, transit, and fitness within a short trip.",
  },
  {
    to: "/ev",
    title: "Should I Own an EV?",
    blurb: "Can you charge an EV at this Toronto address? Checks home charging, or public charging access if home isn't an option.",
  },
  {
    to: "/area",
    title: "Should I Live Here?",
    blurb: "See what's changing near any Toronto address, how it compares on safety, and the maintenance record if it's a rental apartment.",
  },
];

export function Home() {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">Toronto City Tools</h1>
      <p className="mt-2 max-w-2xl text-lg text-ink-2">
        Tools to help citizens of Toronto stay more informed and participate in city-related decisions.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {TOOLS.map((t) => (
          <Link
            key={t.to}
            to={t.to}
            className="group flex min-h-48 flex-col rounded-xl border border-line bg-surface p-5 transition hover:-translate-y-0.5 hover:border-accent focus-visible:outline-2 focus-visible:outline-accent"
          >
            <span className="text-lg font-bold text-ink">{t.title}</span>
            <span className="mt-2 text-sm text-ink-2">{t.blurb}</span>
            <span className="mt-auto pt-4 text-sm font-semibold text-accent">
              Open <span aria-hidden className="inline-block transition group-hover:translate-x-0.5">→</span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
