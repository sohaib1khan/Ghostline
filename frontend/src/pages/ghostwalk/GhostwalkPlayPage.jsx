import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import GhostEditor from "../../components/editor/GhostEditor.jsx";
import { runGhostwalk } from "../../components/editor/sandbox.js";
import MarkdownView from "../../components/content/MarkdownView.jsx";
import { languageLabel } from "../../ghostwalk/languages.js";
import { syntaxFor } from "../../ghostwalk/syntax.js";
import { gameMeta, themeFor, themeMoveMessage } from "../../ghostwalk/themes.js";
import { readPrefs } from "../../prefs.js";
import { playSound } from "../../sounds.js";

const GhostwalkScene = lazy(() => import("./GhostwalkScene.jsx"));

/** Playback pacing — Slow is the default so each move is easy to follow. */
const SPEEDS = [
  { id: "slow", label: "Slow", ms: 1100 },
  { id: "normal", label: "Normal", ms: 650 },
  { id: "fast", label: "Fast", ms: 280 },
  { id: "instant", label: "Instant", ms: 0 },
];

export default function GhostwalkPlayPage() {
  const { slug } = useParams();
  const [search] = useSearchParams();
  const memory = search.get("memory") === "1";
  const prefs = readPrefs();
  const reduce = prefs.reduceMotion;
  const stageRef = useRef(null);

  const [level, setLevel] = useState(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [hintsShown, setHintsShown] = useState(0);
  const [introOpen, setIntroOpen] = useState(true);
  const [syntaxOpen, setSyntaxOpen] = useState(false);
  const [speedId, setSpeedId] = useState(reduce ? "instant" : "slow");
  const [running, setRunning] = useState(false);
  const [loadingEngine, setLoadingEngine] = useState(false);
  const [autoPlay, setAutoPlay] = useState(false);
  const [trace, setTrace] = useState([]);
  const [traceIndex, setTraceIndex] = useState(0);
  const [moves, setMoves] = useState([]);
  const [hero, setHero] = useState(null);
  const [grid, setGrid] = useState([]);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);
  const [actions, setActions] = useState([]);

  const speed = SPEEDS.find((item) => item.id === speedId) || SPEEDS[0];

  useEffect(() => {
    let cancelled = false;
    setError("");
    setResult(null);
    api(`/api/ghostwalk/levels/${slug}${memory ? "?memory=true" : ""}`)
      .then((data) => {
        if (cancelled) return;
        setLevel(data);
        setDraft(data.starter_code || "");
        setGrid(data.grid || []);
        setHero({
          row: data.start?.row ?? 1,
          col: data.start?.col ?? 1,
          facing: data.start?.facing || "E",
        });
        setMoves([]);
        setTrace([]);
        setTraceIndex(0);
        setAutoPlay(false);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, memory]);

  const theme = useMemo(
    () =>
      themeFor(level?.language || "python", {
        farm: level?.mode === "farm",
        contrast: prefs.contrast,
      }),
    [level?.language, level?.mode, prefs.contrast],
  );

  const applyFrame = useCallback(
    (frame, { appendMove = true } = {}) => {
      if (!frame) return;
      setHero({ row: frame.row, col: frame.col, facing: frame.facing });
      if (frame.grid) setGrid(frame.grid);
      if (!appendMove) return;
      const themed = themeMoveMessage(theme, frame);
      if (themed) {
        setMoves((current) => [...current, themed]);
      }
    },
    [theme],
  );

  function focusStage() {
    stageRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
  }

  useEffect(() => {
    if (!trace.length || traceIndex >= trace.length) return undefined;
    applyFrame(trace[traceIndex]);
    if (traceIndex >= trace.length - 1) {
      if (autoPlay) setAutoPlay(false);
      return undefined;
    }
    if (!autoPlay) return undefined;
    const delay = speed.ms;
    if (delay <= 0) {
      const rest = trace.slice(traceIndex + 1);
      rest.forEach((frame) => applyFrame(frame));
      setTraceIndex(trace.length - 1);
      setAutoPlay(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setTraceIndex((value) => value + 1), delay);
    return () => window.clearTimeout(timer);
  }, [trace, traceIndex, speed.ms, applyFrame, autoPlay]);

  async function prepareRun() {
    if (!level || running) return null;
    setRunning(true);
    setLoadingEngine(true);
    setMessage("");
    setResult(null);
    setMoves([]);
    setAutoPlay(false);
    focusStage();
    try {
      const levelPayload = {
        grid: level.grid,
        start: level.start,
        allowed: level.allowed,
        goal: level.goal,
        max_steps: level.max_steps,
      };
      const outcome = await runGhostwalk(levelPayload, draft, level.language || "python");
      setLoadingEngine(false);
      setActions(outcome.actions || []);
      const frames = outcome.trace || [];
      setTrace(frames);
      setTraceIndex(0);
      if (!frames.length && outcome.error) {
        setMessage(outcome.error);
      }
      if (outcome.ok) {
        playSound("correct");
        const submitted = await api(`/api/ghostwalk/levels/${slug}/submit`, {
          method: "POST",
          body: {
            code: draft,
            actions: outcome.actions || [],
            hints_used: hintsShown,
          },
        });
        setResult(submitted);
        if (submitted.ok) {
          setMessage(
            `Cleared · ${"★".repeat(submitted.earned_stars || submitted.stars)} · +${submitted.xp_awarded || 0} XP`,
          );
        } else {
          setMessage(submitted.error || "Server rejected the run.");
        }
      } else {
        playSound("wrong");
        setMessage(outcome.error || "Not quite.");
      }
      return frames;
    } catch (err) {
      setMessage(err.message || "Run failed.");
      return null;
    } finally {
      setLoadingEngine(false);
      setRunning(false);
    }
  }

  async function runCode() {
    const frames = await prepareRun();
    if (frames?.length) {
      setAutoPlay(true);
      setTraceIndex(0);
    }
  }

  async function stepOnce() {
    focusStage();
    if (!trace.length) {
      const frames = await prepareRun();
      if (frames?.length) {
        setAutoPlay(false);
        setTraceIndex(0);
      }
      return;
    }
    if (traceIndex >= trace.length - 1) return;
    setAutoPlay(false);
    setTraceIndex((value) => value + 1);
  }

  function resetWorld() {
    if (!level) return;
    setTrace([]);
    setTraceIndex(0);
    setAutoPlay(false);
    setMoves([]);
    setMessage("");
    setResult(null);
    setGrid(level.grid || []);
    setHero({
      row: level.start?.row ?? 1,
      col: level.start?.col ?? 1,
      facing: level.start?.facing || "E",
    });
    focusStage();
  }

  useEffect(() => {
    function onKey(event) {
      if (event.ctrlKey && event.key === "Enter") {
        event.preventDefault();
        runCode();
      } else if (event.ctrlKey && event.key === ".") {
        event.preventDefault();
        stepOnce();
      } else if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "r") {
        event.preventDefault();
        resetWorld();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const mode = level?.mode || "free";
  const guidedTarget = mode === "guided" && level?.solution ? level.solution : "";
  const unlockedCmds = useMemo(() => (level?.allowed || []).join(", "), [level]);
  const stepLabel =
    trace.length > 0
      ? `Step ${Math.min(traceIndex + 1, trace.length)}/${trace.length}`
      : "Step";

  if (error) {
    return (
      <section className="rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_25%,transparent)] bg-surface p-6">
        <h1 className="text-3xl font-semibold">Ghostwalk</h1>
        <p className="mt-3 text-lg text-error">{error}</p>
        <Link to="/ghostwalk" className="mt-4 inline-flex min-h-12 items-center text-base text-accent">
          Back to map
        </Link>
      </section>
    );
  }

  if (!level) {
    return <p className="text-base text-muted">Loading level…</p>;
  }

  return (
    <section className="ghostwalk-play mx-auto flex w-full max-w-[90rem] flex-col gap-4">
      <header className="rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_18%,transparent)] bg-surface px-4 py-3 sm:px-5">
        <p className="font-mono text-xs uppercase tracking-wider text-accent sm:text-sm">
          {gameMeta(level.language).game} · {gameMeta(level.language).ghost} · Level {level.order}
          {level.mode === "farm" ? " · Ghostfarm" : ""}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{level.title}</h1>
        <p className="mt-1 text-sm text-muted sm:text-base">
          {languageLabel(level.language)} · {level.concept}
        </p>
      </header>

      {/* Sticky stage: scene + controls stay in view while the rest scrolls */}
      <div ref={stageRef} className="ghostwalk-stage sticky top-0 z-20 -mx-1 px-1 sm:mx-0 sm:px-0">
        <div className="ghostwalk-world overflow-hidden rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_22%,transparent)] bg-bg shadow-[var(--shadow)]">
          <Suspense fallback={<p className="p-4 text-base text-muted">Loading world…</p>}>
            <GhostwalkScene
              grid={grid}
              hero={hero}
              reduceMotion={reduce}
              language={level.language || "python"}
              mode={level.mode || "free"}
            />
          </Suspense>
        </div>

        <div
          className="ghostwalk-dock mt-2 flex flex-wrap items-center gap-2 rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_22%,transparent)] bg-surface/95 p-2 backdrop-blur-md sm:gap-3 sm:p-3"
          role="group"
          aria-label="Simulation controls"
        >
          <button
            type="button"
            className="min-h-12 flex-1 rounded-xl bg-accent px-4 text-base font-semibold text-on-accent disabled:opacity-50 sm:flex-none sm:px-5"
            disabled={running}
            onClick={() => runCode()}
          >
            {loadingEngine ? "Running…" : autoPlay ? "Playing…" : "Run"}
          </button>
          <button
            type="button"
            className="min-h-12 flex-1 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_35%,transparent)] px-4 text-base font-medium disabled:opacity-50 sm:flex-none sm:px-5"
            disabled={running || (trace.length > 0 && traceIndex >= trace.length - 1 && !loadingEngine)}
            onClick={() => stepOnce()}
          >
            {stepLabel}
          </button>
          <button
            type="button"
            className="min-h-12 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_35%,transparent)] px-4 text-base font-medium sm:px-5"
            onClick={resetWorld}
          >
            Reset
          </button>
          {level.hints?.length ? (
            <button
              type="button"
              className="min-h-12 rounded-xl border-2 border-accent px-4 text-base font-medium text-accent sm:px-5"
              onClick={() => setHintsShown((count) => Math.min(count + 1, level.hints.length))}
              disabled={hintsShown >= level.hints.length}
            >
              Hint ({hintsShown}/{level.hints.length})
            </button>
          ) : null}
          <label className="flex min-h-12 items-center gap-2 text-sm text-text sm:ml-auto sm:text-base">
            Speed
            <select
              value={speedId}
              onChange={(event) => setSpeedId(event.target.value)}
              className="min-h-12 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_35%,transparent)] bg-bg px-3 text-base text-text"
            >
              {SPEEDS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <p className="font-mono text-sm text-muted sm:text-base" aria-label="Par lines">
            Par {level.par_lines}
          </p>
        </div>

        {message ? (
          <p
            className="mt-2 rounded-xl border-2 border-accent bg-accent/15 px-4 py-3 text-base font-medium text-text sm:text-lg"
            role="status"
          >
            {message}
          </p>
        ) : null}
      </div>

      <div className="rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_22%,transparent)] bg-surface p-4 shadow-[var(--shadow)] sm:p-6">
        <div className="rounded-xl border-2 border-[color-mix(in_srgb,var(--accent)_35%,transparent)] bg-bg/60 p-4">
          <button
            type="button"
            className="min-h-12 text-base font-semibold text-accent"
            onClick={() => setIntroOpen((value) => !value)}
            aria-expanded={introOpen}
          >
            {introOpen ? "Hide intro" : "Show intro"}
          </button>
          {introOpen ? (
            <div className="ghostwalk-intro mt-3 text-base leading-relaxed">
              <MarkdownView text={level.intro_markdown || ""} />
              <p className="mt-3 font-medium text-text">
                Unlocked commands:{" "}
                <span className="font-mono text-accent">{unlockedCmds || "none"}</span>
              </p>
            </div>
          ) : null}
        </div>

        <div className="mt-3 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_18%,transparent)] bg-bg/40 p-4">
          <button
            type="button"
            className="min-h-12 text-base font-semibold text-accent"
            onClick={() => setSyntaxOpen((value) => !value)}
            aria-expanded={syntaxOpen}
          >
            {syntaxOpen ? "Hide syntax this game understands" : "Syntax this game understands"}
          </button>
          {syntaxOpen ? (
            <ul className="mt-3 list-disc space-y-2 pl-5 text-base leading-relaxed text-text">
              {syntaxFor(level.language || "python").map((line) => (
                <li key={line}>
                  <code className="whitespace-pre-wrap font-mono text-sm text-accent">{line}</code>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(14rem,20rem)]">
          <div className="min-w-0">
            <h2 className="mb-2 text-lg font-semibold">Your code</h2>
            <GhostEditor
              key={`${slug}-${memory ? "m" : "n"}`}
              value={draft}
              onChange={setDraft}
              target={guidedTarget}
              ghost=""
              disabled={running}
            />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">Moves</h2>
            <ul
              className="mt-2 max-h-[min(22rem,40vh)] overflow-auto rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_28%,transparent)] bg-bg p-3 text-base leading-snug"
              aria-live="polite"
            >
              {moves.length ? (
                moves.map((item, index) => (
                  <li
                    key={`${index}-${item}`}
                    className={`border-b border-[color-mix(in_srgb,var(--text)_12%,transparent)] py-2 text-text last:border-0 ${
                      index === moves.length - 1 ? "font-medium text-accent" : ""
                    }`}
                  >
                    <span className="font-mono font-semibold text-accent">{index + 1}.</span> {item}
                  </li>
                ))
              ) : (
                <li className="py-2 text-text">Run or Step to watch each move here.</li>
              )}
            </ul>
          </div>
        </div>

        {hintsShown > 0 ? (
          <ul className="mt-4 flex flex-col gap-2">
            {level.hints.slice(0, hintsShown).map((hint) => (
              <li
                key={hint}
                className="rounded-xl border-2 border-[color-mix(in_srgb,var(--accent)_30%,transparent)] bg-bg px-4 py-3 text-base text-text"
              >
                {hint}
              </li>
            ))}
          </ul>
        ) : null}

        {result?.ok && level.mode === "guided" && !memory ? (
          <p className="mt-4 text-base">
            <Link to={`/ghostwalk/${slug}?memory=1`} className="font-semibold text-accent underline">
              Try it from memory
            </Link>{" "}
            — empty editor, free mode.
          </p>
        ) : null}

        <p className="mt-5 text-sm text-muted">
          Drag to look around · scroll to zoom · Ctrl+Enter run · Ctrl+. step · Ctrl+Shift+R reset
          {actions.length ? ` · ${actions.length} actions recorded` : ""}
        </p>
        <Link
          to="/ghostwalk"
          className="mt-2 inline-flex min-h-12 items-center text-base font-medium text-accent underline"
        >
          Back to map
        </Link>
      </div>
    </section>
  );
}
