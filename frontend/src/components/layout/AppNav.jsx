import { NavLink, useLocation } from "react-router-dom";

const LEARN = [
  { to: "/", label: "Home", end: true },
  { to: "/projects", label: "Projects" },
  { to: "/playground", label: "Playground" },
  { to: "/games", label: "Games" },
  { to: "/stats", label: "Stats", end: true },
];

const STUDIO = [
  { to: "/admin/content", label: "Content" },
  { to: "/admin/users", label: "Users", end: true },
];

const GUEST = [
  { to: "/demo", label: "Demo" },
  { to: "/login", label: "Login", end: true },
  { to: "/signup", label: "Sign up", end: true },
];

function keyClass(active) {
  return `inline-flex min-h-10 items-center rounded-full px-3.5 text-sm transition-colors duration-200 ${
    active
      ? "bg-bg text-accent shadow-[0_0_16px_color-mix(in_srgb,var(--accent)_22%,transparent)] ring-1 ring-accent/30"
      : "text-muted hover:text-text"
  }`;
}

function Key({ to, end, children }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => keyClass(isActive)}>
      {children}
    </NavLink>
  );
}

function Group({ label, children }) {
  return (
    <div className="flex items-center gap-1">
      <span className="px-2 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
        {label}
      </span>
      {children}
    </div>
  );
}

export default function AppNav({ user, theme, onTheme, onSignOut, signingOut }) {
  const location = useLocation();
  const nextTheme = theme === "dark" ? "light" : "dark";
  const settingsActive =
    location.pathname.startsWith("/settings") ||
    location.pathname === "/admin/settings" ||
    location.pathname.startsWith("/admin/ai");

  return (
    <nav aria-label="Main" className="max-w-full overflow-x-auto">
      <div className="flex w-max min-w-full items-center gap-1 rounded-2xl border border-accent/15 bg-surface/90 p-1.5 shadow-[var(--shadow)] backdrop-blur-sm">
        {user ? (
          <Group label="Learn">
            {LEARN.map((item) => (
              <Key key={item.to} to={item.to} end={item.end}>
                {item.label}
              </Key>
            ))}
          </Group>
        ) : (
          <Group label="Start">
            {GUEST.map((item) => (
              <Key key={item.to} to={item.to} end={item.end}>
                {item.label}
              </Key>
            ))}
          </Group>
        )}
        {user?.role === "admin" ? (
          <>
            <span className="mx-1 h-6 w-px shrink-0 bg-muted/25" aria-hidden="true" />
            <Group label="Studio">
              {STUDIO.map((item) => (
                <Key key={item.to} to={item.to} end={item.end}>
                  {item.label}
                </Key>
              ))}
            </Group>
          </>
        ) : null}
        <div className="ml-auto flex items-center gap-1 pl-2">
          {user ? (
            <NavLink to="/settings/profile" className={() => keyClass(settingsActive)}>
              Settings
            </NavLink>
          ) : null}
          <button
            type="button"
            className="inline-flex min-h-10 items-center rounded-full px-3.5 text-sm text-muted hover:text-text"
            onClick={onTheme}
            aria-label={`Switch to ${nextTheme} theme`}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          {user ? (
            <button
              type="button"
              onClick={onSignOut}
              disabled={signingOut}
              className="inline-flex min-h-10 items-center rounded-full px-3.5 text-sm text-muted hover:text-text disabled:opacity-50"
            >
              {signingOut ? "Signing out…" : "Sign out"}
            </button>
          ) : null}
        </div>
      </div>
    </nav>
  );
}
