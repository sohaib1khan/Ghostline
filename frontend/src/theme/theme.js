const THEME_KEY = "ghostline-theme";
const THEME_COLORS = { dark: "#1b1f23", light: "#f6f4ef" };

export function readTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return "dark";
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
  // High-contrast preference overrides the calm palette when set.
  try {
    const prefs = JSON.parse(localStorage.getItem("ghostline-preferences") || "{}");
    if (prefs.contrast === "high-dark" || prefs.contrast === "high-light") {
      document.documentElement.dataset.contrast = prefs.contrast;
    } else {
      delete document.documentElement.dataset.contrast;
    }
  } catch {
    delete document.documentElement.dataset.contrast;
  }
  const color = THEME_COLORS[theme] || THEME_COLORS.dark;
  const nodes = document.querySelectorAll('meta[name="theme-color"]');
  if (nodes.length === 0) {
    const meta = document.createElement("meta");
    meta.setAttribute("name", "theme-color");
    meta.setAttribute("content", color);
    document.head.appendChild(meta);
    return;
  }
  nodes.forEach((node) => node.setAttribute("content", color));
}
