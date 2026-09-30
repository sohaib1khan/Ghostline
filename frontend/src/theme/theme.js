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
