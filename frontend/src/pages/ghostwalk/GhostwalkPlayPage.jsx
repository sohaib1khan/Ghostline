import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import GhostEditor from "../../components/editor/GhostEditor.jsx";
import { runGhostwalk } from "../../components/editor/sandbox.js";
import MarkdownView from "../../components/content/MarkdownView.jsx";
import { readPrefs } from "../../prefs.js";
import { playSound } from "../../sounds.js";

const GhostwalkScene = lazy(() => import("./GhostwalkScene.jsx"));

const SPEEDS = [
  { id: "slow", label: "Slow", ms: 700 },
  { id: "normal", label: "Normal", ms: 350 },
  { id: "fast", label: "Fast", ms: 120 },
  { id: "instant", label: "Instant", ms: 0 },
];

function viewButtonClass(active) {
  return [
    "min-h-12 rounded-xl border-2 px-4 text-base font-medium",
    active
      ? "border-accent bg-accent text-on-accent"
      : "border-[color-mix(in_srgb,var(--text)_35%,transparent)] bg-surface text-text",
  ].join(" ");
}

export default function GhostwalkPlayPage() {
  const { slug } = useParams();
  const [search] = useSearchParams();
  const memory = search.get("memory") === "1";
  const prefs = readPrefs();
  const reduce = prefs.reduceMotion;

  const [level, setLevel] = useState(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [hintsShown, setHintsShown] = useState(0);
  const [introOpen, setIntroOpen] = useState(true);
  // Top-down is easier to read when zoomed; keep as default for comfort.
  const [topDown, setTopDown] = useState(true);
  const [speedId, setSpeedId] = useState(reduce ? "instant" : "slow");
  const [running, setRunning] = useState(false);
  const [loadingEngine, setLoadingEngine] = useState(false);
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
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, memory]);

  const applyFrame = useCallback((frame) => {
    if (!frame) return;
    setHero({ row: frame.row, col: frame.col, facing: frame.facing });
    if (frame.grid) setGrid(frame.grid);
    if (frame.message) {
      setMoves((current) => [...current, frame.message]);
    }
  }, []);

  useEffect(() => {
    if (!trace.length || traceIndex >= trace.length) return undefined;
    const frame = trace[traceIndex];
    applyFrame(frame);
    if (traceIndex >= trace.length - 1) return undefined;
    const delay = speed.ms;
    if (delay <= 0) {
      setTraceIndex(trace.length - 1);
      applyFrame(trace[trace.length - 1]);
      return undefined;
    }
    const timer = window.setTimeout(() => setTraceIndex((value) => value + 1), delay);
    return () => window.clearTimeout(timer);
  }, [trace, traceIndex, speed.ms, applyFrame]);

  async function runCode({ stepOnly = false } = {}) {
    if (!level || running) return;
    setRunning(true);
    setLoadingEngine(true);
    setMessage("");
    setResult(null);
    setMoves([]);
    try {
      const levelPayload = {
        grid: level.grid,
        start: level.start,
        allowed: level.allowed,
        goal: level.goal,
        max_steps: level.max_steps,
      };
      const outcome = await runGhostwalk(levelPayload, draft);
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
    } catch (err) {
      setMessage(err.message || "Run failed.");
    } finally {
      setLoadingEngine(false);
      setRunning(false);
    }
  }

  function resetWorld() {
    if (!level) return;
    setTrace([]);
    setTraceIndex(0);
    setMoves([]);
    setMessage("");
    setResult(null);
    setGrid(level.grid || []);
    setHero({
      row: level.start?.row ?? 1,
      col: level.start?.col ?? 1,
      facing: level.start?.facing || "E",
    });
  }

  useEffect(() => {
    function onKey(event) {
      if (event.ctrlKey && event.key === "Enter") {
        event.preventDefault();
        runCode();
      } else if (event.ctrlKey && event.key === ".") {
        event.preventDefault();
        runCode({ stepOnly: true });
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
    <section className="ghostwalk-play flex flex-col gap-5">
      <div className="ghostwalk-world min-h-[18rem] h-[min(48vh,26rem)] sm:h-[min(52vh,32rem)]">
        <Suspense fallback={<p className="p-4 text-base text-muted">Loading world…</p>}>
          <GhostwalkScene grid={grid} hero={hero} topDown={topDown} reduceMotion={reduce} />
        </Suspense>
      </div>

      <div className="flex flex-wrap items-center gap-3" role="group" aria-label="World view controls">
        <button
          type="button"
          className={viewButtonClass(!topDown)}
          onClick={() => setTopDown(false)}
          aria-pressed={!topDown}
        >
          3D view
        </button>
        <button
          type="button"
          className={viewButtonClass(topDown)}
          onClick={() => setTopDown(true)}
          aria-pressed={topDown}
        >
          Top-down
        </button>
        <button type="button" className={viewButtonClass(false)} onClick={resetWorld}>
          Reset view
        </button>
        <label className="ml-auto flex min-h-12 items-center gap-3 text-base text-text">
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
      </div>

      <div className="rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_22%,transparent)] bg-surface p-4 shadow-[var(--shadow)] sm:p-6">
        <p className="font-mono text-sm uppercase tracking-wider text-accent">
          Level {level.order} · {level.concept}
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{level.title}</h1>

        <div className="mt-4 rounded-xl border-2 border-[color-mix(in_srgb,var(--accent)_35%,transparent)] bg-bg/60 p-4">
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

        {/* Stack on narrow / zoomed viewports; side-by-side only when roomy */}
        <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(16rem,22rem)]">
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
              className="mt-2 max-h-[min(28rem,50vh)] overflow-auto rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_28%,transparent)] bg-bg p-3 text-base leading-snug"
              aria-live="polite"
            >
              {moves.length ? (
                moves.map((item, index) => (
                  <li
                    key={`${index}-${item}`}
                    className="border-b border-[color-mix(in_srgb,var(--text)_12%,transparent)] py-2 text-text last:border-0"
                  >
                    <span className="font-mono font-semibold text-accent">{index + 1}.</span> {item}
                  </li>
                ))
              ) : (
                <li className="py-2 text-text">Run your code to see each move here.</li>
              )}
            </ul>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            className="min-h-12 rounded-xl bg-accent px-5 text-base font-semibold text-on-accent disabled:opacity-50"
            disabled={running}
            onClick={() => runCode()}
          >
            {loadingEngine ? "Running…" : "Run"}
          </button>
          <button
            type="button"
            className="min-h-12 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_35%,transparent)] px-5 text-base font-medium disabled:opacity-50"
            disabled={running}
            onClick={() => runCode({ stepOnly: true })}
          >
            Step
          </button>
          <button
            type="button"
            className="min-h-12 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_35%,transparent)] px-5 text-base font-medium"
            onClick={resetWorld}
          >
            Reset
          </button>
          {level.hints?.length ? (
            <button
              type="button"
              className="min-h-12 rounded-xl border-2 border-accent px-5 text-base font-medium text-accent"
              onClick={() => setHintsShown((count) => Math.min(count + 1, level.hints.length))}
              disabled={hintsShown >= level.hints.length}
            >
              Hint ({hintsShown}/{level.hints.length})
            </button>
          ) : null}
          <p className="ml-auto self-center font-mono text-base text-text" aria-label="Par lines">
            Par {level.par_lines} lines
          </p>
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

        {message ? (
          <p
            className="mt-4 rounded-xl border-2 border-accent bg-accent/15 px-4 py-3 text-lg font-medium text-text"
            role="status"
          >
            {message}
          </p>
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
          Shortcuts: Ctrl+Enter run · Ctrl+. step · Ctrl+Shift+R reset
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
