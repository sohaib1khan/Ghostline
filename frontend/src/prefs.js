/** Learner comfort preferences — localStorage for demo; synced to /api/me/preferences when signed in. */

const KEY = "ghostline-preferences";

export const TEXT_SCALES = [100, 125, 150, 175, 200];
export const CODE_SCALES = [100, 125, 150, 175, 200];
export const LINE_SPACINGS = ["normal", "relaxed", "loose"];
export const CONTRASTS = ["calm", "high-dark", "high-light"];
export const GHOST_STRENGTHS = [30, 45, 60, 75];
export const CURSOR_STYLES = ["normal", "thick", "glow"];
export const FOCUS_RINGS = ["standard", "thick"];

/** @deprecated Keep for A−/A+ mapping into codeScale. */
export const TYPING_SCALES = ["md", "lg", "xl"];

export const PREF_DEFAULTS = {
  reduceMotion: false,
  sound: false,
  volume: 0.4,
  textScale: 100,
  // DECISION: large code by default — low-vision users should not hunt for a setting first.
  codeScale: 150,
  lineSpacing: "relaxed",
  contrast: "calm",
  ghostStrength: 60,
  cursorStyle: "thick",
  focusRing: "thick",
  dyslexiaSpacing: false,
  wrapLongLines: true,
  showWhitespace: true,
  highContrastTyping: true,
  editorBodyPx: null,
  // Daily learning goal — reviews to clear and new lessons to finish.
  dailyReviews: 5,
  dailyLessons: 1,
  // Legacy alias used by GhostEditor A−/A+ until fully migrated.
  typingScale: "lg",
};

function clampGoal(value, fallback, max) {
  const n = Math.round(Number(value));
  return Number.isFinite(n) && n >= 0 && n <= max ? n : fallback;
}

function pick(list, value, fallback) {
  return list.includes(value) ? value : fallback;
}

function clampScale(value) {
  const n = Number(value);
  return TEXT_SCALES.includes(n) ? n : PREF_DEFAULTS.textScale;
}

function typingFromCode(codeScale) {
  if (codeScale >= 175) {
    return "xl";
  }
  if (codeScale >= 125) {
    return "lg";
  }
  return "md";
}

function codeFromTyping(typingScale) {
  if (typingScale === "xl") {
    return 175;
  }
  if (typingScale === "md") {
    return 100;
  }
  return 150;
}

function firstVisitDefaults() {
  const next = { ...PREF_DEFAULTS };
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      next.reduceMotion = true;
    }
    if (window.matchMedia("(prefers-contrast: more)").matches) {
      next.contrast = window.matchMedia("(prefers-color-scheme: light)").matches
        ? "high-light"
        : "high-dark";
      next.highContrastTyping = true;
    }
  } catch {
    /* ignore */
  }
  return next;
}

export function normalizePrefs(raw = {}) {
  const parsed = raw && typeof raw === "object" ? raw : {};
  const volume = Number(parsed.volume);
  let codeScale = clampScale(parsed.codeScale);
  if (parsed.codeScale === undefined && parsed.typingScale) {
    codeScale = codeFromTyping(pick(TYPING_SCALES, parsed.typingScale, "lg"));
  }
  const textScale = clampScale(parsed.textScale ?? 100);
  const wrapLongLines =
    parsed.wrapLongLines === undefined ? textScale >= 150 || codeScale >= 150 : Boolean(parsed.wrapLongLines);
  return {
    reduceMotion: Boolean(parsed.reduceMotion),
    sound: Boolean(parsed.sound),
    volume: Number.isFinite(volume) ? Math.min(1, Math.max(0, volume)) : PREF_DEFAULTS.volume,
    textScale,
    codeScale,
    lineSpacing: pick(LINE_SPACINGS, parsed.lineSpacing, PREF_DEFAULTS.lineSpacing),
    contrast: pick(CONTRASTS, parsed.contrast, PREF_DEFAULTS.contrast),
    ghostStrength: pick(GHOST_STRENGTHS, Number(parsed.ghostStrength), PREF_DEFAULTS.ghostStrength),
    cursorStyle: pick(CURSOR_STYLES, parsed.cursorStyle, PREF_DEFAULTS.cursorStyle),
    focusRing: pick(FOCUS_RINGS, parsed.focusRing, PREF_DEFAULTS.focusRing),
    dyslexiaSpacing: Boolean(parsed.dyslexiaSpacing),
    wrapLongLines,
    showWhitespace:
      parsed.showWhitespace === undefined ? PREF_DEFAULTS.showWhitespace : Boolean(parsed.showWhitespace),
    highContrastTyping:
      parsed.highContrastTyping === undefined
        ? PREF_DEFAULTS.highContrastTyping
        : Boolean(parsed.highContrastTyping),
    editorBodyPx: (() => {
      const height = Number(parsed.editorBodyPx);
      return Number.isFinite(height) && height >= 220 ? Math.round(height) : null;
    })(),
    dailyReviews: clampGoal(parsed.dailyReviews, PREF_DEFAULTS.dailyReviews, 50),
    dailyLessons: clampGoal(parsed.dailyLessons, PREF_DEFAULTS.dailyLessons, 20),
    typingScale: typingFromCode(codeScale),
  };
}

export function readPrefs() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) {
      return firstVisitDefaults();
    }
    return normalizePrefs(JSON.parse(raw));
  } catch {
    return { ...PREF_DEFAULTS };
  }
}

export function applyDom(prefs) {
  const root = document.documentElement;
  // DECISION: scale root via % so browser zoom and our text scale multiply cleanly.
  root.style.setProperty("--ui-scale", String((prefs.textScale || 100) / 100));
  root.dataset.reduceMotion = prefs.reduceMotion ? "true" : "false";
  root.dataset.typingScale = prefs.typingScale;
  root.dataset.codeScale = String(prefs.codeScale);
  root.dataset.lineSpacing = prefs.lineSpacing;
  root.dataset.contrast = prefs.contrast;
  root.dataset.ghostStrength = String(prefs.ghostStrength);
  root.dataset.cursorStyle = prefs.cursorStyle;
  root.dataset.focusRing = prefs.focusRing;
  root.dataset.dyslexiaSpacing = prefs.dyslexiaSpacing ? "true" : "false";
  root.dataset.wrapLongLines = prefs.wrapLongLines ? "true" : "false";
  root.dataset.typingContrast = prefs.highContrastTyping || prefs.contrast !== "calm" ? "high" : "normal";
  root.dataset.showWhitespace = prefs.showWhitespace ? "true" : "false";
}

export function writePrefs(next) {
  const prefs = normalizePrefs(next);
  localStorage.setItem(KEY, JSON.stringify(prefs));
  applyDom(prefs);
  window.dispatchEvent(new Event("ghostline-prefs"));
  return prefs;
}

export function bumpTypingScale(delta) {
  const prefs = readPrefs();
  const at = CODE_SCALES.indexOf(prefs.codeScale);
  const next = CODE_SCALES[Math.min(CODE_SCALES.length - 1, Math.max(0, at + delta))];
  return writePrefs({ ...prefs, codeScale: next });
}

export function applyStoredPrefs() {
  return writePrefs(readPrefs());
}

/** Merge server prefs over local after sign-in. */
export function mergeServerPrefs(serverPrefs) {
  if (!serverPrefs || typeof serverPrefs !== "object") {
    return readPrefs();
  }
  return writePrefs({ ...readPrefs(), ...serverPrefs });
}
