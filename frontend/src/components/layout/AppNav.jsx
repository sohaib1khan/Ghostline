import { NavLink, useLocation } from "react-router-dom";
import { isStaff, isSuperAdmin } from "../../roles.js";

const LEARN = [
  { to: "/", label: "Home", end: true, match: (path) => path === "/" },
  {
    to: "/projects",
    label: "Projects",
    match: (path) =>
      path === "/projects" || path.startsWith("/learn/tracks") || path.startsWith("/learn/lessons"),
  },
  {
    to: "/playground",
    label: "Playground",
    match: (path) => path.startsWith("/playground"),
  },
  {
    to: "/games",
    label: "Games",
    match: (path) => path === "/games" || path.startsWith("/games/"),
  },
];

const STUDIO = [
  {
    to: "/admin/content",
    label: "Content",
    match: (path) => path.startsWith("/admin/content") || path.startsWith("/admin/preview"),
  },
  {
    to: "/admin/leaderboard",
    label: "Leaderboard",
    match: (path) => path.startsWith("/admin/leaderboard") || path.startsWith("/admin/leadboard"),
  },
];

const STUDIO_USERS = [
  {
    to: "/admin/users",
    label: "Users",
    end: true,
    match: (path) => path.startsWith("/admin/users"),
  },
];

const GUEST = [
  { to: "/demo", label: "Demo", match: (path) => path === "/demo" || path.startsWith("/demo/") },
  { to: "/login", label: "Login", end: true, match: (path) => path === "/login" },
  { to: "/signup", label: "Sign up", end: true, match: (path) => path === "/signup" },
];

function Key({ to, end, active, children }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={`app-nav-key ${active ? "is-active" : ""}`}
      aria-current={active ? "page" : undefined}
    >
      {children}
    </NavLink>
  );
}

function Segment({ label, tone = "learn", children }) {
  return (
    <div className={`app-nav-segment app-nav-segment--${tone}`}>
      <p className="app-nav-segment-label">{label}</p>
      <div className="app-nav-keys" role="list">
        {children}
      </div>
    </div>
  );
}

export default function AppNav({ user, onSignOut, signingOut }) {
  const location = useLocation();
  const path = location.pathname;
  const staff = isStaff(user?.role);
  const superAdmin = isSuperAdmin(user?.role);
  const studioItems = [...STUDIO, ...(superAdmin ? STUDIO_USERS : [])];
  const settingsActive =
    path.startsWith("/settings") || path === "/admin/settings" || path.startsWith("/admin/ai");

  return (
    <nav aria-label="Main" className="app-nav">
      <div className="app-nav-rail">
        {user ? (
          <Segment label="Learn" tone="learn">
            {LEARN.map((item) => (
              <span key={item.to} role="listitem">
                <Key to={item.to} end={item.end} active={item.match(path)}>
                  {item.label}
                </Key>
              </span>
            ))}
          </Segment>
        ) : (
          <Segment label="Start" tone="learn">
            {GUEST.map((item) => (
              <span key={item.to} role="listitem">
                <Key to={item.to} end={item.end} active={item.match(path)}>
                  {item.label}
                </Key>
              </span>
            ))}
          </Segment>
        )}

        {staff ? (
          <Segment label="Studio" tone="studio">
            {studioItems.map((item) => (
              <span key={item.to} role="listitem">
                <Key to={item.to} end={item.end} active={item.match(path)}>
                  {item.label}
                </Key>
              </span>
            ))}
          </Segment>
        ) : null}

        <div className="app-nav-account">
          {user ? (
            <>
              <Key to="/settings/profile" active={settingsActive}>
                Settings
              </Key>
              <button
                type="button"
                onClick={onSignOut}
                disabled={signingOut}
                className="app-nav-signout"
              >
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </nav>
  );
}
