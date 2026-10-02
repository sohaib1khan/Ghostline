import { NavLink, Outlet, useOutletContext } from "react-router-dom";
import { isStaff } from "../../roles.js";

const YOU = [
  { to: "/settings/profile", label: "Profile", hint: "Name and password" },
  { to: "/settings/preferences", label: "Preferences", hint: "Theme, motion, and sound" },
  { to: "/settings/progress", label: "Progress", hint: "Reset lessons by track or step" },
];

const SITE = [
  { to: "/admin/settings", label: "Leaderboard", hint: "Who can see XP" },
  { to: "/settings/notifications", label: "Notifications", hint: "Where alerts are sent" },
  { to: "/admin/ai", label: "AI", hint: "Draft lessons" },
];

function itemClass(active) {
  return `block rounded-xl px-3 py-2 ${active ? "bg-bg shadow-[var(--shadow)]" : "hover:bg-bg/60"}`;
}

function Section({ title, items }) {
  return (
    <div className="min-w-44 flex-1">
      <p className="px-3 pb-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">{title}</p>
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} end className={({ isActive }) => itemClass(isActive)}>
              <span className="block text-sm text-text">{item.label}</span>
              <span className="block text-xs text-muted">{item.hint}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function SettingsLayout() {
  const context = useOutletContext();
  const admin = isStaff(context.user?.role);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
      <nav
        aria-label="Settings"
        className="flex flex-col gap-5 rounded-2xl bg-surface p-3 shadow-[var(--shadow)] sm:flex-row sm:flex-wrap lg:sticky lg:top-6 lg:flex-col"
      >
        <Section title="You" items={YOU} />
        {admin ? <Section title="Site" items={SITE} /> : null}
      </nav>
      <div className="min-w-0">
        <Outlet context={context} />
      </div>
    </div>
  );
}
