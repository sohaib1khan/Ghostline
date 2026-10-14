/** Indent width by language / file — used by lessons, games, and playground. */

const TWO_SPACE = new Set([
  "javascript",
  "js",
  "web",
  "html",
  "css",
  "json",
  "typescript",
  "ts",
]);

export function indentUnitForTrack(slug) {
  const key = String(slug || "")
    .trim()
    .toLowerCase();
  return TWO_SPACE.has(key) ? 2 : 4;
}

export function indentUnitForPath(filePath) {
  const lower = String(filePath || "").toLowerCase();
  if (/\.(js|mjs|cjs|jsx|ts|tsx|json|html?|css)$/.test(lower)) {
    return 2;
  }
  return 4;
}
