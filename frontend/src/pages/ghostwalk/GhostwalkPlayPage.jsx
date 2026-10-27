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
  const [topDown, setTopDown] = useState(false);
  const [speedId, setSpeedId] = useState(reduce ? "instant" : "normal");
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

  const speed = SPEEDS.find((item) => item.id === speedId) || SPEEDS[1];

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
      setTraceIndex(stepOnly ? 0 : 0);
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
      <section className="rounded-2xl bg-surface p-6">
        <h1 className="text-2xl font-semibold">Ghostwalk</h1>
        <p className="mt-3 text-error">{error}</p>
        <Link to="/ghostwalk" className="mt-4 inline-flex text-accent">
          Back to map
        </Link>
      </section>
    );
  }

  if (!level) {
    return <p className="text-sm text-muted">Loading level…</p>;
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="ghostwalk-world min-h-[240px] h-[min(55vh,28rem)]">
        <Suspense fallback={<p className="p-4 text-sm text-muted">Loading 3D world…</p>}>
          <GhostwalkScene grid={grid} hero={hero} topDown={topDown} reduceMotion={reduce} />
        </Suspense>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm"
          onClick={() => setTopDown(false)}
          aria-pressed={!topDown}
        >
          3D
        </button>
        <button
          type="button"
          className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm"
          onClick={() => setTopDown(true)}
          aria-pressed={topDown}
        >
          Top-down
        </button>
        <button
          type="button"
          className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm"
          onClick={resetWorld}
        >
          Reset view
        </button>
        <label className="ml-auto flex min-h-11 items-center gap-2 text-sm text-muted">
          Speed
          <select
            value={speedId}
            onChange={(event) => setSpeedId(event.target.value)}
            className="rounded-xl border border-muted/30 bg-bg px-2 py-2 text-text"
          >
            {SPEEDS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="rounded-2xl bg-surface p-4 shadow-[var(--shadow)] sm:p-6">
        <p className="font-mono text-[11px] uppercase tracking-wider text-accent">
          Level {level.order} · {level.concept}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{level.title}</h1>

        <div className="mt-3 rounded-xl border border-muted/20 p-3">
          <button
            type="button"
            className="min-h-11 text-sm font-medium text-accent"
            onClick={() => setIntroOpen((value) => !value)}
            aria-expanded={introOpen}
          >
            {introOpen ? "Hide intro" : "Show intro"}
          </button>
          {introOpen ? (
            <div className="mt-2 text-sm">
              <MarkdownView text={level.intro_markdown || ""} />
              <p className="mt-2 text-muted">Unlocked commands: {unlockedCmds || "none"}</p>
            </div>
          ) : null}
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(12rem,18rem)]">
          <div>
            <GhostEditor
              key={`${slug}-${memory ? "m" : "n"}`}
              value={draft}
              onChange={setDraft}
              target={guidedTarget}
              ghost=""
              disabled={running}
            />
          </div>
          <div>
            <h2 className="text-sm font-medium">Moves</h2>
            <ul
              className="mt-2 max-h-64 overflow-auto rounded-xl border border-muted/20 bg-bg p-2 text-sm"
              aria-live="polite"
            >
              {moves.length ? (
                moves.map((item, index) => (
                  <li key={`${index}-${item}`} className="py-1 text-muted">
                    {index + 1}. {item}
                  </li>
                ))
              ) : (
                <li className="text-muted">Run your code to see each move here.</li>
              )}
            </ul>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="min-h-11 rounded-xl bg-accent px-4 text-sm font-medium text-on-accent disabled:opacity-50"
            disabled={running}
            onClick={() => runCode()}
          >
            {loadingEngine ? "Running…" : "Run"}
          </button>
          <button
            type="button"
            className="min-h-11 rounded-xl border border-muted/30 px-4 text-sm disabled:opacity-50"
            disabled={running}
            onClick={() => runCode({ stepOnly: true })}
          >
            Step
          </button>
          <button
            type="button"
            className="min-h-11 rounded-xl border border-muted/30 px-4 text-sm"
            onClick={resetWorld}
          >
            Reset
          </button>
          {level.hints?.length ? (
            <button
              type="button"
              className="min-h-11 rounded-xl border border-muted/30 px-4 text-sm text-accent"
              onClick={() => setHintsShown((count) => Math.min(count + 1, level.hints.length))}
              disabled={hintsShown >= level.hints.length}
            >
              Hint ({hintsShown}/{level.hints.length})
            </button>
          ) : null}
          <p className="ml-auto self-center font-mono text-sm text-muted" aria-label="Par lines">
            ★★☆ par {level.par_lines}
          </p>
        </div>

        {hintsShown > 0 ? (
          <ul className="mt-3 flex flex-col gap-1">
            {level.hints.slice(0, hintsShown).map((hint) => (
              <li key={hint} className="text-sm text-muted">
                {hint}
              </li>
            ))}
          </ul>
        ) : null}

        {message ? (
          <p className="mt-3 text-sm" role="status">
            {message}
          </p>
        ) : null}

        {result?.ok && level.mode === "guided" && !memory ? (
          <p className="mt-3 text-sm">
            <Link to={`/ghostwalk/${slug}?memory=1`} className="text-accent">
              Try it from memory
            </Link>{" "}
            — empty editor, free mode.
          </p>
        ) : null}

        <p className="mt-4 text-xs text-muted">
          Shortcuts: Ctrl+Enter run · Ctrl+. step · Ctrl+Shift+R reset · actions recorded:{" "}
          {actions.length}
        </p>
        <Link to="/ghostwalk" className="mt-2 inline-flex min-h-11 items-center text-sm text-accent">
          Back to map
        </Link>
      </div>
    </section>
  );
}
