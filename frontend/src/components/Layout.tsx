import { NavLink, Outlet } from "react-router";

const NAV = [
  { to: "/city", label: "City Scorecard" },
  { to: "/ev", label: "Should I Own an EV?" },
  { to: "/area", label: "Should I Live Here?" },
];

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-bold text-ink">
            <img src="/favicon.svg" alt="" className="h-6 w-6" />
            Toronto City Tools
          </NavLink>
          <nav className="-mx-1 flex gap-1 overflow-x-auto text-sm">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-2.5 py-1.5 font-medium ${isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink"}`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-line py-4 text-center text-xs text-ink-muted">
        Data: OpenStreetMap contributors, City of Toronto Open Data, Toronto Police Service, NREL. Scores are
        directional, not advice.
      </footer>
    </div>
  );
}
