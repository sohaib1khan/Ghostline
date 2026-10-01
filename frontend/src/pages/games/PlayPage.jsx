import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import WorkedExample from "../../components/content/WorkedExample.jsx";
import FillGap from "../../components/editor/FillGap.jsx";
import { fillAnswer } from "../../components/editor/fill.js";
import GhostEditor from "../../components/editor/GhostEditor.jsx";
import XpPop from "../../components/feedback/XpPop.jsx";
import { readPrefs } from "../../prefs.js";
import { playSound } from "../../sounds.js";

export default function PlayPage() {
  const { game } = useParams();
  const [params] = useSearchParams();
  const track = params.get("track") || "";
  const maxRounds = Math.max(1, Number(params.get("rounds") || 10) || 10);
  const [round, setRound] = useState(null);
  const [count, setCount] = useState(1);
  const [passedCount, setPassedCount] = useState(0);
  const [draft, setDraft] = useState("");
  const [blanks, setBlanks] = useState({});
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [finished, setFinished] = useState(false);
  const [hintsShown, setHintsShown] = useState(0);
  const [studying, setStudying] = useState(false);
  const systemReduce = useReducedMotion();
  const reduce = Boolean(systemReduce) || readPrefs().reduceMotion;

  useEffect(() => {
    let cancelled = false;
    const query = new URLSearchParams({ game, track });
    api(`/api/games/next?${query}`)
      .then((data) => {
        if (!cancelled) {
          setRound(data);
          setRemaining(data.time_limit_seconds || 0);
          setStudying(Boolean(data.example));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [game, track]);

  const expired =
    game === "command_roulette" && remaining <= 0 && !result?.passed && !studying;

  useEffect(() => {
    if (game !== "command_roulette" || !remaining || result?.passed || studying) {
      return undefined;
    }
    const timer = window.setTimeout(() => setRemaining((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [game, remaining, result?.passed, round?.exercise_id, studying]);

  async function loadNext() {
    setPending(true);
    setError("");
    try {
      const query = new URLSearchParams({ game, track, exclude: round.exercise_id });
      const data = await api(`/api/games/next?${query}`);
      setRound(data);
      setDraft("");
      setBlanks({});
      setResult(null);
      setMessage("");
      setHintsShown(0);
      setRemaining(data.time_limit_seconds || 0);
      setStudying(Boolean(data.example));
      setCount((value) => value + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function submit(attempt, stats) {
    // Soft miss stays editable — only a pass (or timer expiry) locks the round.
    if (!round || pending || result?.passed || expired) {
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const body = { game, attempt, hints_used: hintsShown };
      if (stats) {
        body.wpm = stats.wpm;
        body.accuracy = stats.accuracy;
        if (stats.duration_seconds) {
          body.duration_seconds = stats.duration_seconds;
        }
      }
      const data = await api(`/api/games/score/${round.exercise_id}`, { method: "POST", body });
      setResult(data);
      if (data.passed) {
        setPassedCount((value) => value + 1);
        playSound(count >= maxRounds ? "complete" : "correct");
      } else {
        playSound("wrong");
        setMessage(data.failed_rule_hint || "Not quite — try a hint.");
        if (round.hints?.length && hintsShown < round.hints.length) {
          setHintsShown((value) => Math.min(value + 1, round.hints.length));
        }
      }
    } catch (err) {
      setMessage(err.message);
    } finally {
      setPending(false);
    }
  }

  if (error) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <p className="text-sm text-error">{error}</p>
        <p className="mt-3 text-sm text-muted">
          Games only use published exercises. Publish imported lessons on Content, then come back.
        </p>
        <Link to="/games" className="mt-4 inline-block text-sm text-accent">
          Back to games
        </Link>
      </section>
    );
  }
  if (!round) {
    return <p className="text-sm text-muted">Loading…</p>;
  }
  if (finished) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">Session done</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Nice work</h1>
        <p className="mt-2 text-sm text-muted">
          {passedCount} of {count} passed · pool had {round.pool_size} published exercises.
        </p>
        <div className="mt-6 flex flex-wrap gap-4 text-sm">
          <Link to="/games" className="text-accent">
            Play again
          </Link>
          <Link to="/" className="text-muted">
            Home
          </Link>
        </div>
      </section>
    );
  }

  const answer =
    game === "fill_frenzy" ? fillAnswer(round.code, round.blanks || [], blanks) : draft;
  const progress = Math.min(100, Math.round((count / maxRounds) * 100));
  const locked = pending || expired || Boolean(result?.passed);

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <Link to="/games" className="text-sm text-accent">
        Games
      </Link>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted">
            Round {count}
            {maxRounds < 900 ? ` of ${maxRounds}` : ""} · pool {round.pool_size}
          </p>
          {round.lesson_title ? (
            <p className="mt-1 text-xs text-muted">From “{round.lesson_title}”</p>
          ) : null}
        </div>
        {game === "command_roulette" && round.time_limit_seconds && !studying ? (
          <p className={`font-mono text-sm ${remaining <= 8 ? "text-error pulse-urgent" : "text-muted"}`}>
            {remaining}s
          </p>
        ) : null}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted/20">
        <div className="session-bar h-full rounded-full bg-accent" style={{ width: `${progress}%` }} />
      </div>
      <p className="mt-4 text-base">{round.prompt}</p>

      {studying && round.example ? (
        <div className="mt-4">
          <WorkedExample
            code={round.example}
            tokens={round.tokens || []}
            reduceMotion={reduce}
            onStart={() => setStudying(false)}
          />
        </div>
      ) : (
        <>
          {game === "bug_hunt" ? (
            <div className="mt-4">
              <p className="text-xs uppercase tracking-wider text-muted">Broken line</p>
              <pre className="mt-2 overflow-x-auto rounded-xl bg-bg px-4 py-3 font-mono text-sm text-error ghost-breathe">
                {round.broken}
              </pre>
              <p className="mt-2 text-xs text-muted">Type the fixed line below — do not copy the typo.</p>
            </div>
          ) : null}
          <div className="mt-4">
            {game === "fill_frenzy" ? (
              <FillGap
                code={round.code}
                blanks={round.blanks || []}
                values={blanks}
                onChange={setBlanks}
                disabled={locked}
              />
            ) : (
              <GhostEditor
                key={round.exercise_id}
                value={draft}
                onChange={setDraft}
                target={game === "speed_drill" ? round.code : ""}
                tokens={round.tokens || []}
                disabled={locked}
                onComplete={(stats) => submit(round.code, stats)}
              />
            )}
          </div>
          {round.hints?.length ? (
            <div className="mt-4">
              <ul className="flex flex-col gap-1">
                {round.hints.slice(0, hintsShown).map((hint) =>
                  reduce ? (
                    <li key={hint} className="text-sm text-muted">
                      {hint}
                    </li>
                  ) : (
                    <motion.li
                      key={hint}
                      className="text-sm text-muted"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      {hint}
                    </motion.li>
                  ),
                )}
              </ul>
              {hintsShown < round.hints.length ? (
                <button
                  type="button"
                  className="mt-2 text-sm text-accent"
                  onClick={() => setHintsShown((value) => value + 1)}
                >
                  Hint ({hintsShown}/{round.hints.length})
                </button>
              ) : null}
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {game !== "speed_drill" ? (
              <button
                type="button"
                disabled={locked}
                onClick={() => submit(answer)}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
              >
                {pending ? "Checking…" : "Check"}
              </button>
            ) : null}
            {result?.passed || expired ? (
              <button
                type="button"
                className="text-sm text-accent"
                onClick={() => {
                  if (count >= maxRounds) {
                    setFinished(true);
                  } else {
                    loadNext();
                  }
                }}
              >
                {count >= maxRounds ? "Finish" : "Next"}
              </button>
            ) : (
              <>
                {result && !result.passed ? (
                  <button
                    type="button"
                    className="text-sm text-muted"
                    onClick={() => {
                      if (count >= maxRounds) {
                        setFinished(true);
                      } else {
                        loadNext();
                      }
                    }}
                  >
                    Skip
                  </button>
                ) : null}
                <button type="button" className="text-sm text-muted" onClick={() => setFinished(true)}>
                  End session
                </button>
              </>
            )}
          </div>
        </>
      )}
      {expired ? <p className="mt-3 text-sm text-muted">Time is up.</p> : null}
      {message ? <p className="mt-3 text-sm text-error">{message}</p> : null}
      {result?.passed ? (
        <div className="mt-3" role="status">
          <XpPop amount={result.xp_awarded} reduce={reduce} />
          <p className="text-success">Passed. {result.xp_total} XP total</p>
        </div>
      ) : null}
    </section>
  );
}
