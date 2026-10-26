import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client.js";
import { SubmitButton } from "../../components/layout/Field.jsx";
import {
  CODE_SCALES,
  CONTRASTS,
  CURSOR_STYLES,
  FOCUS_RINGS,
  GHOST_STRENGTHS,
  LINE_SPACINGS,
  TEXT_SCALES,
  mergeServerPrefs,
  readPrefs,
  writePrefs,
} from "../../prefs.js";
import { applyTheme } from "../../theme/theme.js";

export default function PreferencesPage() {
  const { theme, setTheme, user } = useOutletContext();
  const [prefs, setPrefs] = useState(readPrefs);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!user) {
        return;
      }
      try {
        const remote = await api("/api/me/preferences");
        if (!cancelled) {
          setPrefs(mergeServerPrefs(remote));
        }
      } catch {
        /* keep local prefs when offline */
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function save(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setNotice("");
    const saved = writePrefs(prefs);
    setPrefs(saved);
    if (user) {
      try {
        const remote = await api("/api/me/preferences", {
          method: "PUT",
          body: saved,
        });
        setPrefs(mergeServerPrefs(remote));
        setNotice("Preferences saved on this device and your account.");
      } catch (err) {
        setError(err.message || "Saved locally, but the server sync failed.");
        setNotice("Preferences saved on this device.");
      } finally {
        setPending(false);
      }
      return;
    }
    setNotice("Preferences saved on this device.");
    setPending(false);
  }

  function field(key, value) {
    setPrefs((current) => ({ ...current, [key]: value }));
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Preferences</h1>
      <p className="mt-2 text-sm text-muted">
        Comfort settings for reading and typing. Signed-in accounts sync these across devices.
      </p>
      <form className="mt-6 flex max-w-xl flex-col gap-6" onSubmit={save}>
        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Appearance</legend>
          <label className="block text-sm text-muted" htmlFor="theme">
            Theme
            <select
              id="theme"
              value={theme}
              onChange={(event) => {
                setTheme(event.target.value);
                applyTheme(event.target.value);
              }}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </label>
        </fieldset>

        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Accessibility</legend>
          <p className="text-sm text-muted">
            Scales the whole app and the practice editor so zoomed browsers stay usable.
          </p>
          <label className="block text-sm text-muted" htmlFor="text-scale">
            Text size
            <select
              id="text-scale"
              value={prefs.textScale}
              onChange={(event) => field("textScale", Number(event.target.value))}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {TEXT_SCALES.map((scale) => (
                <option key={scale} value={scale}>
                  {scale}%
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-muted" htmlFor="code-scale">
            Code font size
            <select
              id="code-scale"
              value={prefs.codeScale}
              onChange={(event) => field("codeScale", Number(event.target.value))}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {CODE_SCALES.map((scale) => (
                <option key={scale} value={scale}>
                  {scale}%
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-muted" htmlFor="line-spacing">
            Line spacing
            <select
              id="line-spacing"
              value={prefs.lineSpacing}
              onChange={(event) => field("lineSpacing", event.target.value)}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {LINE_SPACINGS.map((item) => (
                <option key={item} value={item}>
                  {item === "normal" ? "Normal" : item === "relaxed" ? "Relaxed (1.6)" : "Loose (1.9)"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-muted" htmlFor="contrast">
            Contrast
            <select
              id="contrast"
              value={prefs.contrast}
              onChange={(event) => field("contrast", event.target.value)}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {CONTRASTS.map((item) => (
                <option key={item} value={item}>
                  {item === "calm"
                    ? "Calm (current theme)"
                    : item === "high-dark"
                      ? "High contrast (dark)"
                      : "High contrast (light)"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-muted" htmlFor="ghost-strength">
            Ghost text strength
            <select
              id="ghost-strength"
              value={prefs.ghostStrength}
              onChange={(event) => field("ghostStrength", Number(event.target.value))}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {GHOST_STRENGTHS.map((item) => (
                <option key={item} value={item}>
                  {item}%
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-muted" htmlFor="cursor-style">
            Cursor
            <select
              id="cursor-style"
              value={prefs.cursorStyle}
              onChange={(event) => field("cursorStyle", event.target.value)}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {CURSOR_STYLES.map((item) => (
                <option key={item} value={item}>
                  {item === "normal"
                    ? "Normal"
                    : item === "thick"
                      ? "Thick block"
                      : "Thick block with slow glow"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-muted" htmlFor="focus-ring">
            Focus ring
            <select
              id="focus-ring"
              value={prefs.focusRing}
              onChange={(event) => field("focusRing", event.target.value)}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {FOCUS_RINGS.map((item) => (
                <option key={item} value={item}>
                  {item === "standard" ? "Standard" : "Extra thick"}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="wrap-lines">
            <input
              id="wrap-lines"
              type="checkbox"
              checked={prefs.wrapLongLines}
              onChange={(event) => field("wrapLongLines", event.target.checked)}
            />
            Wrap long lines in the editor
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="show-whitespace">
            <input
              id="show-whitespace"
              type="checkbox"
              checked={prefs.showWhitespace !== false}
              onChange={(event) => field("showWhitespace", event.target.checked)}
            />
            Show spaces and indent levels (· marks)
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="typing-contrast">
            <input
              id="typing-contrast"
              type="checkbox"
              checked={prefs.highContrastTyping}
              onChange={(event) => field("highContrastTyping", event.target.checked)}
            />
            High-contrast typing frame
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="dyslexia-spacing">
            <input
              id="dyslexia-spacing"
              type="checkbox"
              checked={prefs.dyslexiaSpacing}
              onChange={(event) => field("dyslexiaSpacing", event.target.checked)}
            />
            Dyslexia-friendly spacing for prose
          </label>
        </fieldset>

        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Learning</legend>
          <p className="text-sm text-muted">
            A small daily goal shown on Home. Zero turns that part off.
          </p>
          <label className="block text-sm text-muted" htmlFor="daily-reviews">
            Daily reviews
            <input
              id="daily-reviews"
              type="number"
              inputMode="numeric"
              min="0"
              max="50"
              value={prefs.dailyReviews}
              onChange={(event) => field("dailyReviews", Number(event.target.value))}
              className="mt-1 block min-h-11 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            />
          </label>
          <label className="block text-sm text-muted" htmlFor="daily-lessons">
            Daily new lessons
            <input
              id="daily-lessons"
              type="number"
              inputMode="numeric"
              min="0"
              max="20"
              value={prefs.dailyLessons}
              onChange={(event) => field("dailyLessons", Number(event.target.value))}
              className="mt-1 block min-h-11 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            />
          </label>
        </fieldset>

        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Motion</legend>
          <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="reduce-motion">
            <input
              id="reduce-motion"
              type="checkbox"
              checked={prefs.reduceMotion}
              onChange={(event) => field("reduceMotion", event.target.checked)}
            />
            Reduce motion
          </label>
        </fieldset>

        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Sound</legend>
          <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="sound">
            <input
              id="sound"
              type="checkbox"
              checked={prefs.sound}
              onChange={(event) => field("sound", event.target.checked)}
            />
            Sound
          </label>
          <p className="text-sm text-muted">
            Sound stays off until you turn it on. Key ticks, a correct chime, and a lesson-complete
            tone use the volume below.
          </p>
          <label className="block text-sm text-muted" htmlFor="volume">
            Volume
            <input
              id="volume"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={prefs.volume}
              disabled={!prefs.sound}
              onChange={(event) => field("volume", Number(event.target.value))}
              className="mt-2 block w-full"
            />
          </label>
        </fieldset>
        {notice ? (
          <p className="text-sm text-success" role="status">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className="text-sm text-error" role="status">
            {error}
          </p>
        ) : null}
        <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save preferences"}</SubmitButton>
      </form>
    </section>
  );
}
