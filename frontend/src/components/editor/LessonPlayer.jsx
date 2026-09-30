import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import {
  clearPracticeSession,
  readExerciseState,
  sessionForLesson,
  sessionHasWork,
  setSessionIndex,
  upsertExerciseState,
} from "../../practiceSession.js";
import MarkdownView from "../content/MarkdownView.jsx";
import WorkedExample from "../content/WorkedExample.jsx";
import { readPrefs } from "../../prefs.js";
import { playSound } from "../../sounds.js";
import XpPop from "../feedback/XpPop.jsx";
import FillGap from "./FillGap.jsx";
import { fillAnswer } from "./fill.js";
import GhostEditor from "./GhostEditor.jsx";
import { runInSandbox } from "./sandbox.js";
import SimulatedTerminal from "./SimulatedTerminal.jsx";

function firstOpen(exercises) {
  const index = exercises.findIndex((item) => item.progress?.status !== "completed");
  return index === -1 ? 0 : index;
}

function needsStudy(exercise) {
  return (
    (exercise?.type === "recall" || exercise?.type === "challenge") &&
    Boolean(String(exercise?.code || "").trim())
  );
}

function freshExerciseState(exercise) {
  return {
    draft: "",
    blanks: {},
    hintsShown: 0,
    result: null,
    message: "",
    burst: 0,
    remaining: exercise?.time_limit_seconds || 0,
    studying: needsStudy(exercise),
  };
}

function hydrateExerciseState(lessonId, exercise) {
  const saved = readExerciseState(lessonId, exercise.id);
  if (!saved) {
    return freshExerciseState(exercise);
  }
  return {
    draft: saved.draft || "",
    blanks: saved.blanks && typeof saved.blanks === "object" ? saved.blanks : {},
    hintsShown: Number(saved.hintsShown) || 0,
    result: saved.result || null,
    message: "",
    burst: 0,
    remaining:
      saved.remaining !== undefined && saved.remaining !== null
        ? Number(saved.remaining)
        : exercise?.time_limit_seconds || 0,
    studying: Boolean(saved.studying),
  };
}

export default function LessonPlayer({
  lesson,
  backTo,
  checkPath,
  onPassed,
  accountXp = true,
  finish = null,
}) {
  const systemReduce = useReducedMotion();
  const alive = useRef(true);
  const startIndex = firstOpen(lesson.exercises);
  const existing = sessionForLesson(lesson.id);
  const [prefs, setPrefs] = useState(readPrefs);
  const [phase, setPhase] = useState(() =>
    sessionHasWork(existing, startIndex) ? "ask" : "ready",
  );
  const [index, setIndex] = useState(() =>
    sessionHasWork(existing, startIndex) ? existing.index : startIndex,
  );
  const exercise = lesson.exercises[index];
  const initial = hydrateExerciseState(lesson.id, lesson.exercises[index] || lesson.exercises[0]);
  const [draft, setDraft] = useState(initial.draft);
  const [blanks, setBlanks] = useState(initial.blanks);
  const [hintsShown, setHintsShown] = useState(initial.hintsShown);
  const [result, setResult] = useState(initial.result);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [remaining, setRemaining] = useState(initial.remaining);
  const [attemptKey, setAttemptKey] = useState(0);
  const [burst, setBurst] = useState(0);
  const [studying, setStudying] = useState(initial.studying);
  // DECISION: never auto-advance after a pass. Next stays disabled briefly so a
  // fast Check click cannot land on the newly shown button.
  const [nextReady, setNextReady] = useState(false);
  const nextLesson = lesson.next_lesson || null;
  const hasNextExercise = index < lesson.exercises.length - 1;

  useEffect(() => {
    if (!result?.passed || !hasNextExercise) {
      setNextReady(false);
      return undefined;
    }
    setNextReady(false);
    const timer = window.setTimeout(() => {
      if (alive.current) {
        setNextReady(true);
      }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [result?.passed, hasNextExercise, exercise?.id]);

  useEffect(() => {
    alive.current = true;
    function sync() {
      setPrefs(readPrefs());
    }
    window.addEventListener("ghostline-prefs", sync);
    return () => {
      alive.current = false;
      window.removeEventListener("ghostline-prefs", sync);
    };
  }, []);

  useEffect(() => {
    if (phase !== "ready" || !exercise) {
      return;
    }
    upsertExerciseState(lesson.id, index, exercise.id, {
      draft,
      blanks,
      hintsShown,
      result,
      studying,
      remaining,
    });
  }, [
    phase,
    lesson.id,
    index,
    exercise?.id,
    draft,
    blanks,
    hintsShown,
    result,
    studying,
    remaining,
  ]);

  useEffect(() => {
    if (
      phase !== "ready" ||
      exercise?.type !== "challenge" ||
      !exercise.time_limit_seconds ||
      result?.passed ||
      studying
    ) {
      return undefined;
    }
    if (remaining <= 0) {
      return undefined;
    }
    const timer = window.setTimeout(() => setRemaining((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [
    attemptKey,
    exercise?.id,
    exercise?.time_limit_seconds,
    exercise?.type,
    phase,
    remaining,
    result?.passed,
    studying,
  ]);

  function applyState(next) {
    setDraft(next.draft);
    setBlanks(next.blanks);
    setHintsShown(next.hintsShown);
    setResult(next.result);
    setMessage(next.message);
    setBurst(next.burst);
    setRemaining(next.remaining);
    setStudying(next.studying);
    setNextReady(Boolean(next.result?.passed));
  }

  function goTo(nextIndex) {
    if (!exercise) {
      return;
    }
    upsertExerciseState(lesson.id, index, exercise.id, {
      draft,
      blanks,
      hintsShown,
      result,
      studying,
      remaining,
    });
    const nextExercise = lesson.exercises[nextIndex];
    setIndex(nextIndex);
    setSessionIndex(lesson.id, nextIndex);
    setAttemptKey(0);
    applyState(hydrateExerciseState(lesson.id, nextExercise));
  }

  function resumeSession() {
    const session = sessionForLesson(lesson.id);
    const nextIndex = session ? Math.min(session.index, lesson.exercises.length - 1) : startIndex;
    setIndex(nextIndex);
    applyState(hydrateExerciseState(lesson.id, lesson.exercises[nextIndex]));
    setAttemptKey(0);
    setPhase("ready");
  }

  function startFresh() {
    clearPracticeSession();
    setIndex(startIndex);
    applyState(freshExerciseState(lesson.exercises[startIndex]));
    setAttemptKey(0);
    setPhase("ready");
  }

  function endSession() {
    clearPracticeSession();
  }

  const reduce = Boolean(systemReduce) || prefs.reduceMotion;
  if (!exercise) {
    return <p className="text-sm text-muted">This lesson has no exercises yet.</p>;
  }

  if (phase === "ask") {
    return (
      <article className="min-w-0 rounded-2xl bg-surface p-4 shadow-[var(--shadow)] sm:p-6">
        {backTo ? (
          <Link to={backTo} className="text-sm text-accent">
            {lesson.track_name}
          </Link>
        ) : (
          <p className="text-sm text-muted">{lesson.track_name}</p>
        )}
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{lesson.title}</h1>
        <div className="mt-6 rounded-xl border border-accent/25 bg-bg/80 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Open session</p>
          <p className="mt-2 text-sm text-muted">
            You left mid-practice on this lesson. Pick up where you left off, or start clean.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent"
              onClick={resumeSession}
            >
              Continue where I left off
            </button>
            <button type="button" className="text-sm text-muted" onClick={startFresh}>
              Start over
            </button>
          </div>
        </div>
      </article>
    );
  }

  const expired =
    exercise.type === "challenge" && remaining <= 0 && !result?.passed && !studying;
  const answer =
    exercise.type === "fill" ? fillAnswer(exercise.code, exercise.blanks || [], blanks) : draft;
  const progressPct = Math.round(
    ((index + (result?.passed ? 1 : 0)) / lesson.exercises.length) * 100,
  );

  async function submit(attempt, stats) {
    setPending(true);
    setMessage("");
    try {
      let output;
      if (exercise.runtime === "browser_js" || exercise.runtime === "pyodide") {
        const ran = await runInSandbox(exercise.runtime, attempt);
        if (!alive.current) {
          return;
        }
        if (ran.error === "timeout") {
          setMessage("Stopped after 3 seconds. The page is still here.");
          return;
        }
        output = ran.output;
      }
      const body = {
        attempt,
        hints_used: hintsShown,
      };
      if (stats) {
        body.wpm = stats.wpm;
        body.accuracy = stats.accuracy;
      }
      if (output !== undefined) {
        body.output = output;
      }
      const path = checkPath ? checkPath(exercise.id) : `/api/check/${exercise.id}`;
      const data = await api(path, { method: "POST", body });
      if (!alive.current) {
        return;
      }
      setResult(data);
      upsertExerciseState(lesson.id, index, exercise.id, {
        draft: attempt,
        blanks,
        hintsShown,
        result: data,
        studying: false,
        remaining,
      });
      if (data.passed && onPassed) {
        onPassed(exercise.id);
      }
      if (data.passed) {
        const last = index >= lesson.exercises.length - 1;
        playSound(last ? "complete" : "correct");
        setBurst(accountXp ? data.xp_awarded || 0 : 0);
      } else {
        playSound("wrong");
        setBurst(0);
      }
      if (!data.passed) {
        setMessage(data.failed_rule_hint || "Not quite — try a hint.");
        if (exercise.hints?.length && hintsShown < exercise.hints.length) {
          setHintsShown((count) => Math.min(count + 1, exercise.hints.length));
        }
      }
    } catch (error) {
      if (alive.current) {
        setMessage(error.message);
      }
    } finally {
      if (alive.current) {
        setPending(false);
      }
    }
  }

  const card = (
    <div className="rounded-xl border border-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          {index + 1} of {lesson.exercises.length} · {exercise.type}
          {exercise.progress?.status === "completed" || result?.passed ? " · done" : ""}
        </p>
        <span className="type-chip font-mono text-xs uppercase tracking-wider text-accent">
          {exercise.type}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted/20">
        <div
          className="lesson-bar h-full rounded-full bg-accent"
          style={{ width: `${progressPct}%` }}
        />
      </div>
      <p className="mt-3 text-xs text-muted">Guided practice — study, type, hint when you stall.</p>
      <p className="mt-3">{exercise.prompt}</p>
      {studying ? (
        <div className="mt-4">
          <WorkedExample
            code={exercise.code}
            tokens={exercise.tokens || []}
            reduceMotion={reduce}
            onStart={() => setStudying(false)}
          />
        </div>
      ) : (
        <>
          {exercise.type === "trace" ? (
            <div className="mt-3 md:hidden">
              <p className="text-sm text-muted">Best on a keyboard.</p>
              {exercise.tokens?.length ? (
                <ul className="mt-3 flex flex-col gap-2">
                  {exercise.tokens.map((token, tokenIndex) => (
                    <li
                      key={`${token.match}-${tokenIndex}`}
                      className={`rounded-xl bg-bg px-3 py-2 ${reduce ? "" : "token-rise"}`}
                      style={reduce ? undefined : { animationDelay: `${tokenIndex * 70}ms` }}
                    >
                      <p className="font-mono text-sm">{token.match}</p>
                      <p className="mt-1 text-sm text-muted">{token.explain}</p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {exercise.type === "challenge" && exercise.time_limit_seconds ? (
            <p
              className={`mt-2 font-mono text-sm ${
                remaining <= 8 ? "text-error pulse-urgent" : "text-muted"
              }`}
            >
              {remaining}s
            </p>
          ) : null}
          <div className="mt-4">
            {exercise.type === "fill" ? (
              <FillGap
                code={exercise.code}
                blanks={exercise.blanks || []}
                values={blanks}
                onChange={setBlanks}
                disabled={pending || expired || Boolean(result?.passed)}
              />
            ) : (
              <GhostEditor
                key={`${exercise.id}-${attemptKey}`}
                value={draft}
                onChange={setDraft}
                target={exercise.type === "trace" ? exercise.code : ""}
                tokens={exercise.tokens || []}
                disabled={pending || expired || Boolean(result?.passed)}
                onComplete={(stats) => submit(exercise.code, stats)}
              />
            )}
          </div>
          {exercise.hints?.length ? (
            <div className="mt-4">
              <p className="text-xs text-muted">
                Stuck? Open a hint — each one costs a little XP when you pass.
              </p>
              <ul className="mt-2 flex flex-col gap-1">
                {exercise.hints.slice(0, hintsShown).map((hint, hintIndex) =>
                  reduce ? (
                    <li key={`${hint}-${hintIndex}`} className="hint-card text-sm text-muted">
                      {hint}
                    </li>
                  ) : (
                    <motion.li
                      key={`${hint}-${hintIndex}`}
                      className="hint-card text-sm text-muted"
                      initial={hintIndex === hintsShown - 1 ? { opacity: 0, y: 10 } : false}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      {hint}
                    </motion.li>
                  ),
                )}
              </ul>
              {hintsShown < exercise.hints.length ? (
                <button
                  type="button"
                  className="mt-2 text-sm text-accent"
                  onClick={() => setHintsShown((count) => count + 1)}
                >
                  Hint ({hintsShown}/{exercise.hints.length})
                </button>
              ) : hintsShown > 0 ? (
                <p className="mt-2 text-xs text-muted">All hints are open.</p>
              ) : null}
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {exercise.type !== "trace" ? (
              <button
                type="button"
                disabled={pending || expired || Boolean(result?.passed)}
                onClick={() => submit(answer)}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
              >
                {pending ? "Checking…" : "Check"}
              </button>
            ) : null}
            {needsStudy(exercise) && !result?.passed ? (
              <button type="button" className="text-sm text-muted" onClick={() => setStudying(true)}>
                Show example again
              </button>
            ) : null}
            {expired ? (
              <button
                type="button"
                className="text-sm text-accent"
                onClick={() => {
                  applyState(freshExerciseState(exercise));
                  setAttemptKey((value) => value + 1);
                  upsertExerciseState(lesson.id, index, exercise.id, {
                    draft: "",
                    blanks: {},
                    hintsShown: 0,
                    result: null,
                    studying: needsStudy(exercise),
                    remaining: exercise.time_limit_seconds || 0,
                  });
                }}
              >
                Try again
              </button>
            ) : null}
            {index > 0 ? (
              <button type="button" className="text-sm text-muted" onClick={() => goTo(index - 1)}>
                Back
              </button>
            ) : null}
          </div>
        </>
      )}
      {message ? (
        <p className="mt-3 text-sm text-error" role="status">
          {message}
        </p>
      ) : null}
      {exercise.type === "trace" && message && !result?.passed ? (
        <button
          type="button"
          className="mt-2 text-sm text-accent"
          onClick={() => submit(exercise.code)}
        >
          Try the check again
        </button>
      ) : null}
      {result?.passed ? (
        <div className="mt-4" role="status">
          <XpPop amount={burst} reduce={reduce} />
          <p className="text-success">
            {accountXp
              ? `Passed. +${result.xp_awarded} XP${
                  result.xp_total !== undefined ? ` · ${result.xp_total} total` : ""
                }`
              : "Passed."}
          </p>
          {exercise.simulated_output ? (
            <SimulatedTerminal text={exercise.simulated_output} reduceMotion={reduce} />
          ) : null}
          {hasNextExercise ? (
            <button
              type="button"
              className="mt-3 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
              disabled={!nextReady}
              onClick={() => goTo(index + 1)}
            >
              Next
            </button>
          ) : finish ? (
            <div className="mt-3 text-sm text-muted" onClickCapture={endSession}>
              {finish}
            </div>
          ) : nextLesson ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Link
                to={`/learn/lessons/${nextLesson.id}`}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent"
                onClick={endSession}
              >
                Continue{nextLesson.title ? `: ${nextLesson.title}` : ""}
              </Link>
              {backTo ? (
                <Link to={backTo} className="text-sm text-muted" onClick={endSession}>
                  Back to path
                </Link>
              ) : null}
            </div>
          ) : reduce ? (
            <p className="mt-3 text-sm text-muted">
              Lesson complete.
              {backTo ? (
                <>
                  {" "}
                  <Link to={backTo} className="text-accent" onClick={endSession}>
                    Back to path
                  </Link>
                </>
              ) : null}
            </p>
          ) : (
            <motion.p
              className="mt-3 text-sm text-muted"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              Lesson complete.
              {backTo ? (
                <>
                  {" "}
                  <Link to={backTo} className="text-accent" onClick={endSession}>
                    Back to path
                  </Link>
                </>
              ) : null}
            </motion.p>
          )}
        </div>
      ) : null}
      {expired ? <p className="mt-3 text-sm text-muted">Time is up.</p> : null}
    </div>
  );

  return (
    <article className="min-w-0 rounded-2xl bg-surface p-4 shadow-[var(--shadow)] sm:p-6">
      {backTo ? (
        <Link to={backTo} className="text-sm text-accent">
          {lesson.track_name}
        </Link>
      ) : (
        <p className="text-sm text-muted">{lesson.track_name}</p>
      )}
      <h1 className={`mt-2 text-2xl font-semibold tracking-tight ${reduce ? "" : "practice-rise"}`}>
        {lesson.title}
      </h1>
      {lesson.level_label ? (
        <p className="mt-2 font-mono text-xs uppercase tracking-[0.16em] text-accent">
          {lesson.level_label}
          {lesson.module_title ? ` · ${lesson.module_title}` : ""}
        </p>
      ) : null}
      {lesson.summary ? <p className="mt-2 text-sm text-muted">{lesson.summary}</p> : null}
      <div className="mt-6">
        <MarkdownView text={lesson.body_markdown} />
      </div>
      <div className="mt-6">
        {reduce ? (
          card
        ) : (
          <motion.div
            key={exercise.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            {card}
          </motion.div>
        )}
      </div>
    </article>
  );
}
