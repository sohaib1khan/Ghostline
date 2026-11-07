/** Preselected bug categories for the report form. */

export const BUG_CATEGORIES = [
  { id: "page_broken", label: "Page won't load or looks broken" },
  { id: "check_failed", label: "Check / submit failed" },
  { id: "editor_typing", label: "Editor or typing issue" },
  { id: "ghostwalk_games", label: "Ghostwalk or games broken" },
  { id: "wrong_content", label: "Wrong content or answer" },
  { id: "account_access", label: "Account or login problem" },
  { id: "other", label: "Something else" },
];

export const TICKET_STATUSES = [
  { id: "open", label: "Open" },
  { id: "waiting_on_user", label: "Waiting on you" },
  { id: "resolved", label: "Resolved" },
  { id: "closed", label: "Closed" },
];

export function categoryLabel(id) {
  return BUG_CATEGORIES.find((item) => item.id === id)?.label || id;
}

export function statusLabel(id) {
  return TICKET_STATUSES.find((item) => item.id === id)?.label || id;
}

/** Snapshot of what the user was doing when they hit Report. */
export function captureBugContext() {
  const path = `${window.location.pathname}${window.location.search || ""}`;
  return {
    page_url: window.location.href.slice(0, 500),
    page_path: path.slice(0, 300),
    user_agent: (navigator.userAgent || "").slice(0, 400),
    viewport: `${window.innerWidth}x${window.innerHeight}`.slice(0, 40),
    context_json: JSON.stringify({
      path,
      theme: document.documentElement.dataset.theme || "",
      online: navigator.onLine,
      language: navigator.language || "",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      captured_at: new Date().toISOString(),
    }).slice(0, 4000),
  };
}
