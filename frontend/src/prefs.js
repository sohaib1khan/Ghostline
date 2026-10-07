const KEY = "ghostline-preferences";

export const TYPING_SCALES = ["md", "lg", "xl"];

export const PREF_DEFAULTS = {
  reduceMotion: false,
  sound: false,
  volume: 0.4,
  // DECISION: large typing by default — one-eye / low-vision users should not
  // hunt for a preference before the first lesson feels readable.
  typingScale: "lg",
  highContrastTyping: true,
};

function clampScale(value) {
  return TYPING_SCALES.includes(value) ? value : PREF_DEFAULTS.typingScale;
}

export function readPrefs() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "{}");
    const volume = Number(parsed.volume);
    return {
      reduceMotion: Boolean(parsed.reduceMotion),
      sound: Boolean(parsed.sound),
      volume: Number.isFinite(volume) ? Math.min(1, Math.max(0, volume)) : PREF_DEFAULTS.volume,
      typingScale: clampScale(parsed.typingScale),
      highContrastTyping:
        parsed.highContrastTyping === undefined
          ? PREF_DEFAULTS.highContrastTyping
          : Boolean(parsed.highContrastTyping),
    };
  } catch {
    return { ...PREF_DEFAULTS };
  }
}

function applyDom(prefs) {
  document.documentElement.dataset.reduceMotion = prefs.reduceMotion ? "true" : "false";
  document.documentElement.dataset.typingScale = prefs.typingScale;
  document.documentElement.dataset.typingContrast = prefs.highContrastTyping ? "high" : "normal";
}

export function writePrefs(next) {
  const prefs = {
    reduceMotion: Boolean(next.reduceMotion),
    sound: Boolean(next.sound),
    volume: Math.min(1, Math.max(0, Number(next.volume) || 0)),
    typingScale: clampScale(next.typingScale),
    highContrastTyping: Boolean(next.highContrastTyping),
  };
  localStorage.setItem(KEY, JSON.stringify(prefs));
  applyDom(prefs);
  window.dispatchEvent(new Event("ghostline-prefs"));
  return prefs;
}

export function bumpTypingScale(delta) {
  const prefs = readPrefs();
  const at = TYPING_SCALES.indexOf(prefs.typingScale);
  const next = TYPING_SCALES[Math.min(TYPING_SCALES.length - 1, Math.max(0, at + delta))];
  return writePrefs({ ...prefs, typingScale: next });
}

export function applyStoredPrefs() {
  return writePrefs(readPrefs());
}
