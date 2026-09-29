const KEY = "ghostline-preferences";

export const PREF_DEFAULTS = {
  reduceMotion: false,
  sound: false,
  volume: 0.4,
};

export function readPrefs() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "{}");
    const volume = Number(parsed.volume);
    return {
      reduceMotion: Boolean(parsed.reduceMotion),
      sound: Boolean(parsed.sound),
      volume: Number.isFinite(volume) ? Math.min(1, Math.max(0, volume)) : PREF_DEFAULTS.volume,
    };
  } catch {
    return { ...PREF_DEFAULTS };
  }
}

export function writePrefs(next) {
  const prefs = {
    reduceMotion: Boolean(next.reduceMotion),
    sound: Boolean(next.sound),
    volume: Math.min(1, Math.max(0, Number(next.volume) || 0)),
  };
  localStorage.setItem(KEY, JSON.stringify(prefs));
  document.documentElement.dataset.reduceMotion = prefs.reduceMotion ? "true" : "false";
  window.dispatchEvent(new Event("ghostline-prefs"));
  return prefs;
}

export function applyStoredPrefs() {
  return writePrefs(readPrefs());
}
