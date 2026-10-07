import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { SubmitButton } from "../../components/layout/Field.jsx";
import { readPrefs, writePrefs } from "../../prefs.js";
import { applyTheme } from "../../theme/theme.js";

export default function PreferencesPage() {
  const { theme, setTheme } = useOutletContext();
  const [prefs, setPrefs] = useState(readPrefs);
  const [notice, setNotice] = useState("");

  function save(event) {
    event.preventDefault();
    setPrefs(writePrefs(prefs));
    setNotice("Preferences saved.");
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Preferences</h1>
      <p className="mt-2 text-sm text-muted">How Ghostline looks, moves, and sounds on this device.</p>
      <form className="mt-6 flex max-w-md flex-col gap-6" onSubmit={save}>
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
          <legend className="text-sm font-medium text-text">Vision & typing</legend>
          <p className="text-sm text-muted">
            Larger type, a thicker caret, and stronger contrast in the practice editor. You can
            also change size with A− / A+ on the typing frame.
          </p>
          <label className="block text-sm text-muted" htmlFor="typing-scale">
            Typing size
            <select
              id="typing-scale"
              value={prefs.typingScale}
              onChange={(event) => setPrefs({ ...prefs, typingScale: event.target.value })}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              <option value="md">Comfortable</option>
              <option value="lg">Large (recommended)</option>
              <option value="xl">Extra large</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm" htmlFor="typing-contrast">
            <input
              id="typing-contrast"
              type="checkbox"
              checked={prefs.highContrastTyping}
              onChange={(event) =>
                setPrefs({ ...prefs, highContrastTyping: event.target.checked })
              }
            />
            High-contrast typing frame
          </label>
        </fieldset>
        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Motion</legend>
          <label className="flex items-center gap-2 text-sm" htmlFor="reduce-motion">
            <input
              id="reduce-motion"
              type="checkbox"
              checked={prefs.reduceMotion}
              onChange={(event) => setPrefs({ ...prefs, reduceMotion: event.target.checked })}
            />
            Reduce motion
          </label>
        </fieldset>
        <fieldset className="flex flex-col gap-3 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Sound</legend>
          <label className="flex items-center gap-2 text-sm" htmlFor="sound">
            <input
              id="sound"
              type="checkbox"
              checked={prefs.sound}
              onChange={(event) => setPrefs({ ...prefs, sound: event.target.checked })}
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
              onChange={(event) => setPrefs({ ...prefs, volume: Number(event.target.value) })}
              className="mt-2 block w-full"
            />
          </label>
        </fieldset>
        {notice ? <p className="text-sm text-success">{notice}</p> : null}
        <SubmitButton>Save preferences</SubmitButton>
      </form>
    </section>
  );
}
