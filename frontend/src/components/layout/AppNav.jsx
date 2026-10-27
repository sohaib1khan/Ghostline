import { useEffect, useId, useState } from "react";
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
    to: "/certificates",
    label: "Certificates",
    match: (path) => path.startsWith("/certificates"),
  },
  {
    to: "/playground",
    label: "Playground",
    match: (path) => path.startsWith("/playground"),
  },
  {
    to: "/ghostwalk",
    label: "Ghostwalk",
    match: (path) => path.startsWith("/ghostwalk"),
  },
  {
    to: "/games",
    label: "Games",
    match: (path) => path === "/games" || path.startsWith("/games/"),
  },
];

const STUDIO = [
  {
    to: "/admin/leaderboard",
    label: "Leaderboard",
    match: (path) => path.startsWith("/admin/leaderboard") || path.startsWith("/admin/leadboard"),
  },
];

const STUDIO_SUPER = [
  {
    to: "/admin/content",
    label: "Content",
    match: (path) => path.startsWith("/admin/content") || path.startsWith("/admin/preview"),
  },
  {
    to: "/admin/ghostwalk",
    label: "Ghostwalk",
    match: (path) => path.startsWith("/admin/ghostwalk"),
  },
  {
    to: "/admin/users",
    label: "Users",
    end: true,
    match: (path) => path.startsWith("/admin/users"),
  },
];

const GUEST = [
  { to: "/demo", label: "Demo", match: (path) => path === "/demo" || path.startsWith("/demo/") },
  { to: "/login", label: "Log in", end: true, match: (path) => path === "/login" },
  { to: "/signup", label: "Sign up", end: true, match: (path) => path === "/signup" },
];

function Key({ to, end, active, children, onNavigate }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={`app-nav-key ${active ? "is-active" : ""}`}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
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
  const menuId = useId();
  const [open, setOpen] = useState(false);
  const staff = isStaff(user?.role);
  const superAdmin = isSuperAdmin(user?.role);
  const studioItems = [...STUDIO, ...(superAdmin ? STUDIO_SUPER : [])];
  const settingsActive =
    path.startsWith("/settings") ||
    path === "/admin/settings" ||
    path.startsWith("/admin/ai") ||
    path.startsWith("/admin/certificates");

  useEffect(() => {
    setOpen(false);
  }, [path]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function onKey(event) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function closeMenu() {
    setOpen(false);
  }

  const learnItems = user ? LEARN : GUEST;
  const learnLabel = user ? "Learn" : "Start";

  return (
    <nav aria-label="Main" className={`app-nav ${open ? "is-open" : ""}`}>
      <div className="app-nav-bar">
        <p className="app-nav-current" aria-live="polite">
          {learnItems.find((item) => item.match(path))?.label ||
            studioItems.find((item) => item.match(path))?.label ||
            (settingsActive ? "Settings" : "Menu")}
        </p>
        <button
          type="button"
          className="app-nav-toggle"
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Close menu" : "Open menu"}
        </button>
      </div>

      <div id={menuId} className="app-nav-rail">
        <Segment label={learnLabel} tone="learn">
          {learnItems.map((item) => (
            <span key={item.to} role="listitem">
              <Key to={item.to} end={item.end} active={item.match(path)} onNavigate={closeMenu}>
                {item.label}
              </Key>
            </span>
          ))}
        </Segment>

        {staff ? (
          <Segment label="Studio" tone="studio">
            {studioItems.map((item) => (
              <span key={item.to} role="listitem">
                <Key to={item.to} end={item.end} active={item.match(path)} onNavigate={closeMenu}>
                  {item.label}
                </Key>
              </span>
            ))}
          </Segment>
        ) : null}

        <div className="app-nav-account">
          {user ? (
            <>
              <Key to="/settings/profile" active={settingsActive} onNavigate={closeMenu}>
                Settings
              </Key>
              <button
                type="button"
                onClick={() => {
                  closeMenu();
                  onSignOut();
                }}
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
