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

const ALPHA = "abcdefghijklmnopqrstuvwxyz".split("");

function SessionChrome({ game, count, maxRounds, round, remaining, studying, children }) {
  const progress = Math.min(100, Math.round((count / maxRounds) * 100));
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
          <p
            className={`font-mono text-sm ${remaining <= 8 ? "text-error pulse-urgent" : "text-muted"}`}
          >
            {remaining}s
          </p>
        ) : null}
        {game === "ghost_race" && round.ghost_wpm ? (
          <p className="font-mono text-sm text-muted">Ghost {round.ghost_wpm} WPM</p>
        ) : null}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted/20">
        <div className="session-bar h-full rounded-full bg-accent" style={{ width: `${progress}%` }} />
      </div>
      <p className="mt-4 text-base">{round.prompt}</p>
      {children}
    </section>
  );
}

function GuideBlock({ guide, open, onToggle }) {
  if (!guide) {
    return null;
  }
  return (
    <div className="mt-4 rounded-xl border border-muted/20 bg-bg/60 px-4 py-3">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 text-left text-sm"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className="font-medium text-text">{guide.title || "How to play"}</span>
        <span className="font-mono text-xs text-muted">{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div className="mt-3 space-y-2 text-sm text-muted">
          <p>{guide.how}</p>
          {guide.example ? (
            <p>
              <span className="text-text">{guide.track} example:</span>{" "}
              <span className="font-mono text-text">{guide.example}</span>
            </p>
          ) : null}
          {guide.example_note ? <p>{guide.example_note}</p> : null}
          {guide.tip ? <p className="text-xs">{guide.tip}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

function HintsBlock({ round, hintsShown, setHintsShown, reduce, locked, onHintCost }) {
  if (!round.hints?.length) {
    return null;
  }
  return (
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
      {hintsShown < round.hints.length && !locked ? (
        <button
          type="button"
          className="mt-2 text-sm text-accent"
          onClick={() => {
            setHintsShown((value) => value + 1);
            // First reveal is free; later clicks cost.
            if (hintsShown >= 1 && onHintCost) {
              onHintCost();
            }
          }}
        >
          Hint ({hintsShown}/{round.hints.length}) — costs points
        </button>
      ) : null}
    </div>
  );
}

function RoundActions({
  game,
  pending,
  locked,
  result,
  expired,
  stuck,
  count,
  maxRounds,
  onCheck,
  onNext,
  onSkip,
  onEnd,
  onTryAgain,
  onSeeAnswer,
  revealedAnswer,
  hideCheck,
}) {
  return (
    <div className="mt-5 flex flex-wrap items-center gap-3">
      {!hideCheck && game !== "speed_drill" && game !== "ghost_race" && !expired ? (
        <button
          type="button"
          disabled={locked}
          onClick={onCheck}
          className="btn-primary disabled:opacity-50"
        >
          {pending ? "Checking…" : "Check"}
        </button>
      ) : null}
      {result?.passed ? (
        <button type="button" className="btn-primary" onClick={onNext}>
          {count >= maxRounds ? "Finish session" : "Next round"}
        </button>
      ) : null}
      {stuck && !result?.passed ? (
        <>
          <button type="button" className="btn-primary" onClick={onTryAgain} disabled={pending}>
            Try again
          </button>
          {!revealedAnswer ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={onSeeAnswer}
              disabled={pending}
            >
              See answer
            </button>
          ) : null}
          <button type="button" className="btn-secondary" onClick={onSkip}>
            {count >= maxRounds ? "Finish session" : "Next round"}
          </button>
          <button type="button" className="btn-ghost" onClick={onEnd}>
            End session
          </button>
        </>
      ) : null}
      {!result?.passed && !stuck ? (
        <button type="button" className="btn-ghost" onClick={onEnd}>
          End session
        </button>
      ) : null}
    </div>
  );
}

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
  const [letters, setLetters] = useState([]);
  const [hangman, setHangman] = useState(null);
  const [codeleRows, setCodeleRows] = useState([]);
  const [codeleDraft, setCodeleDraft] = useState("");
  const [flipped, setFlipped] = useState([]);
  const [matched, setMatched] = useState([]);
  const [scrambleLines, setScrambleLines] = useState([]);
  const [snakePath, setSnakePath] = useState([]);
  const [crossword, setCrossword] = useState({});
  const [board, setBoard] = useState(Array(9).fill(null));
  const [bossHp, setBossHp] = useState(8);
  const [bossHealth, setBossHealth] = useState(8);
  const [guideOpen, setGuideOpen] = useState(true);
  const [revealedAnswer, setRevealedAnswer] = useState("");
  const [assistOpen, setAssistOpen] = useState(false);
  const systemReduce = useReducedMotion();
  const reduce = Boolean(systemReduce) || readPrefs().reduceMotion;

  function resetModeState(data) {
    setDraft("");
    setBlanks({});
    setResult(null);
    setMessage("");
    setHintsShown(data.hints?.length ? 1 : 0);
    setRemaining(data.time_limit_seconds || 0);
    setStudying(Boolean(data.example));
    setLetters([]);
    setHangman(null);
    setCodeleRows([]);
    setCodeleDraft("");
    setFlipped([]);
    setMatched([]);
    setScrambleLines(data.lines ? data.lines.map((line) => ({ ...line })) : []);
    setSnakePath([]);
    setCrossword({});
    setGuideOpen(true);
    setRevealedAnswer("");
    setAssistOpen(false);
    if (game === "boss_battle") {
      setBossHp(data.boss_hp || 8);
      setBossHealth(data.boss_hp || 8);
    }
  }

  useEffect(() => {
    let cancelled = false;
    const query = new URLSearchParams({ game, track });
    api(`/api/games/next?${query}`)
      .then((data) => {
        if (!cancelled) {
          setRound(data);
          resetModeState(data);
          if (game === "tic_tac_toe") {
            setBoard(Array(9).fill(null));
          }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [game, track]);

  const expired =
    game === "command_roulette" && remaining <= 0 && !result?.passed && !studying;
  const stuck = Boolean(expired || (result && !result.passed) || assistOpen);

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
      resetModeState(data);
      setCount((value) => value + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  function advanceOrFinish() {
    if (count >= maxRounds) {
      setFinished(true);
    } else {
      loadNext();
    }
  }

  function tryAgain() {
    if (!round) {
      return;
    }
    setResult(null);
    setAssistOpen(false);
    setMessage(
      revealedAnswer
        ? "Try typing the answer yourself — no rush."
        : "Timer reset. Give it another go.",
    );
    setRemaining(round.time_limit_seconds || 0);
    setStudying(false);
    setPending(false);
  }

  async function seeAnswer() {
    if (!round || pending) {
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const data = await api(`/api/games/score/${round.exercise_id}`, {
        method: "POST",
        body: {
          game,
          attempt: "",
          phase: "reveal",
          hints_used: Math.max(round.hints?.length || 1, hintsShown),
        },
      });
      const answer = data.revealed_answer || "";
      setRevealedAnswer(answer);
      setAssistOpen(true);
      if (round.hints?.length) {
        setHintsShown(round.hints.length);
      }
      setResult(null);
      setMessage(data.failed_rule_hint || "Answer shown — try again when you are ready.");
      setRemaining(round.time_limit_seconds || 0);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setPending(false);
    }
  }

  async function submit(attempt, stats, extra = {}) {
    if (!round || pending || result?.passed || expired) {
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const body = {
        game,
        attempt,
        hints_used: Math.max(0, hintsShown - 1),
        phase: extra.phase || "submit",
        letters: extra.letters || [],
      };
      if (stats) {
        body.wpm = stats.wpm;
        body.accuracy = stats.accuracy;
        if (stats.duration_seconds) {
          body.duration_seconds = stats.duration_seconds;
        }
      }
      const data = await api(`/api/games/score/${round.exercise_id}`, { method: "POST", body });
      if (extra.phase === "probe") {
        setHangman(data);
        if (data.solved || data.passed) {
          setResult(data);
          setPassedCount((value) => value + 1);
          playSound(count >= maxRounds ? "complete" : "correct");
        } else if (data.lives_left === 0) {
          setMessage("The ghost faded — try again, or see the answer.");
          playSound("wrong");
          setAssistOpen(true);
          setResult({ ...data, passed: false });
        }
        return data;
      }
      setResult(data);
      if (data.feedback) {
        setCodeleRows((rows) => [
          ...rows,
          { guess: data.guess, feedback: data.feedback },
        ]);
        setCodeleDraft("");
      }
      if (data.passed) {
        setPassedCount((value) => value + 1);
        playSound(count >= maxRounds ? "complete" : "correct");
        if (game === "boss_battle") {
          setBossHp((hp) => Math.max(0, hp - 1));
        }
        if (game === "tic_tac_toe" && typeof extra.cellIndex === "number") {
          setBoard((cells) => {
            const next = [...cells];
            next[extra.cellIndex] = "X";
            return next;
          });
        }
      } else {
        playSound("wrong");
        setMessage(data.failed_rule_hint || "Not quite — try again.");
        setAssistOpen(true);
        if (round.hints?.length && hintsShown < round.hints.length) {
          setHintsShown((value) => Math.min(value + 1, round.hints.length));
        }
        if (game === "boss_battle") {
          setBossHealth((hp) => Math.max(0, hp - 1));
        }
        if (game === "tic_tac_toe" && typeof extra.cellIndex === "number") {
          setBoard((cells) => {
            const next = [...cells];
            next[extra.cellIndex] = "O";
            return next;
          });
        }
      }
      return data;
    } catch (err) {
      setMessage(err.message);
      return null;
    } finally {
      setPending(false);
    }
  }

  async function guessHangmanLetter(ch) {
    if (letters.includes(ch) || result?.passed || pending) {
      return;
    }
    const next = [...letters, ch];
    setLetters(next);
    await submit("", null, { phase: "probe", letters: next });
  }

  function flipCard(id) {
    if (matched.includes(id) || flipped.includes(id) || flipped.length >= 2 || result?.passed) {
      return;
    }
    const next = [...flipped, id];
    setFlipped(next);
    if (next.length < 2) {
      return;
    }
    const cards = round.cards || [];
    const [a, b] = next.map((cardId) => cards.find((card) => card.id === cardId));
    if (a && b && a.pair === b.pair) {
      const done = [...matched, a.id, b.id];
      setMatched(done);
      setFlipped([]);
      if (done.length >= (round.pair_count || 0) * 2) {
        submit("done");
      }
    } else {
      window.setTimeout(() => setFlipped([]), 700);
    }
  }

  function moveScramble(index, dir) {
    setScrambleLines((rows) => {
      const next = [...rows];
      const target = index + dir;
      if (target < 0 || target >= next.length) {
        return rows;
      }
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function eatToken(token) {
    if (result?.passed || pending) {
      return;
    }
    const next = [...snakePath, token];
    setSnakePath(next);
    if (next.length >= (round.target_len || 0)) {
      submit(next.join(" "));
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

  const locked = pending || expired || Boolean(result?.passed);
  const fillMode =
    game === "fill_frenzy" ||
    (game === "tic_tac_toe" && round.cell?.kind === "fill") ||
    (game === "boss_battle" && round.mode === "fill") ||
    (game === "query_detective" && round.blanks);
  const answer = fillMode
    ? fillAnswer(round.code || round.scaffold || "", round.blanks || [], blanks)
    : draft;
  const mask = hangman?.mask || round.pattern || [];
  const wrong = hangman?.wrong || [];
  const lives = hangman?.lives_left ?? 6;
  const ghostOpacity = Math.max(0.15, lives / 6);

  return (
    <SessionChrome
      game={game}
      count={count}
      maxRounds={maxRounds}
      round={round}
      remaining={remaining}
      studying={studying}
    >
      <GuideBlock
        guide={round.guide}
        open={guideOpen}
        onToggle={() => setGuideOpen((value) => !value)}
      />
      {game === "boss_battle" ? (
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wider text-muted">
            Boss {bossHp} HP · You {bossHealth} HP
          </p>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted/20">
            <div
              className="h-full rounded-full bg-accent transition-all"
              style={{ width: `${(bossHp / (round.boss_hp || 8)) * 100}%` }}
            />
          </div>
        </div>
      ) : null}

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

          {game === "code_hangman" ? (
            <div className="mt-4">
              <div
                className="hangman-ghost mx-auto h-28 w-28 rounded-full bg-muted/15 transition-opacity"
                style={{ opacity: ghostOpacity }}
                aria-hidden
              />
              <p className="mt-4 text-center font-mono text-2xl tracking-[0.35em]">
                {mask.map((ch, index) => (
                  <span key={`${ch}-${index}`}>{ch === " " ? "\u00a0" : ch}</span>
                ))}
              </p>
              <p className="mt-2 text-center text-xs text-muted">
                Lives {lives}/6
                {wrong.length ? ` · miss ${wrong.join(" ").toUpperCase()}` : ""}
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                {ALPHA.map((ch) => {
                  const used = letters.includes(ch);
                  return (
                    <button
                      key={ch}
                      type="button"
                      disabled={used || locked}
                      onClick={() => guessHangmanLetter(ch)}
                      className="h-9 w-9 rounded-lg border border-muted/30 font-mono text-sm uppercase disabled:opacity-30"
                    >
                      {ch}
                    </button>
                  );
                })}
              </div>
              <form
                className="mt-4 flex flex-wrap items-center justify-center gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (draft.trim()) {
                    submit(draft.trim());
                  }
                }}
              >
                <input
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  disabled={locked}
                  placeholder="Or type the full keyword"
                  className="min-w-48 rounded-xl border border-muted/30 bg-bg px-3 py-2 font-mono text-sm"
                  aria-label="Type the keyword"
                  autoComplete="off"
                />
                <button
                  type="submit"
                  disabled={locked || !draft.trim()}
                  className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
                >
                  Guess word
                </button>
              </form>
            </div>
          ) : null}

          {game === "codele" ? (
            <div className="mt-4">
              <div className="mx-auto flex max-w-xs flex-col gap-1.5">
                {Array.from({ length: round.max_guesses || 6 }).map((_, rowIndex) => {
                  const row = codeleRows[rowIndex];
                  const active = !row && rowIndex === codeleRows.length;
                  const chars = row
                    ? row.guess.padEnd(5).split("")
                    : active
                      ? codeleDraft.padEnd(5).split("")
                      : Array(5).fill("");
                  return (
                    <div key={rowIndex} className="grid grid-cols-5 gap-1.5">
                      {chars.map((ch, col) => {
                        const state = row?.feedback?.[col];
                        const tone =
                          state === "correct"
                            ? "border-success bg-success/20 text-success"
                            : state === "present"
                              ? "border-accent bg-accent/15 text-accent"
                              : state === "absent"
                                ? "border-muted/40 bg-muted/10 text-muted"
                                : "border-muted/30";
                        return (
                          <span
                            key={col}
                            className={`flex h-10 items-center justify-center rounded-md border font-mono text-sm font-semibold uppercase ${tone}`}
                          >
                            {ch.trim()}
                          </span>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
              {!result?.passed && codeleRows.length < (round.max_guesses || 6) ? (
                <form
                  className="mt-4 flex flex-wrap items-center justify-center gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (codeleDraft.trim().length >= 1) {
                      submit(codeleDraft);
                    }
                  }}
                >
                  <input
                    value={codeleDraft}
                    onChange={(event) =>
                      setCodeleDraft(event.target.value.replace(/[^A-Za-z]/g, "").slice(0, 5))
                    }
                    maxLength={5}
                    disabled={locked}
                    className="w-36 rounded-xl border border-muted/30 bg-bg px-3 py-2 font-mono uppercase tracking-widest"
                    aria-label="Codele guess"
                    autoComplete="off"
                  />
                  <button
                    type="submit"
                    disabled={locked || codeleDraft.length < 5}
                    className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
                  >
                    Guess
                  </button>
                </form>
              ) : null}
            </div>
          ) : null}

          {game === "memory_match" ? (
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {(round.cards || []).map((card) => {
                const open = flipped.includes(card.id) || matched.includes(card.id);
                return (
                  <button
                    key={card.id}
                    type="button"
                    disabled={open || locked}
                    onClick={() => flipCard(card.id)}
                    className={`min-h-20 rounded-xl border px-3 py-3 text-left text-sm transition ${
                      matched.includes(card.id)
                        ? "border-success/40 bg-success/10 text-success"
                        : open
                          ? "border-accent/40 bg-bg"
                          : "border-muted/25 bg-muted/10 text-muted"
                    }`}
                  >
                    {open ? card.text : "?"}
                  </button>
                );
              })}
            </div>
          ) : null}

          {game === "code_crossword" ? (
            <ul className="mt-4 space-y-3">
              {(round.clues || []).map((clue) => (
                <li key={clue.id}>
                  <p className="text-sm text-muted">
                    {clue.id + 1}. {clue.clue}{" "}
                    <span className="font-mono text-xs">({clue.length})</span>
                  </p>
                  <input
                    value={crossword[clue.id] || ""}
                    onChange={(event) =>
                      setCrossword((prev) => ({ ...prev, [clue.id]: event.target.value }))
                    }
                    maxLength={clue.length}
                    disabled={locked}
                    className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 font-mono text-sm"
                    aria-label={`Clue ${clue.id + 1}`}
                  />
                </li>
              ))}
            </ul>
          ) : null}

          {game === "syntax_snake" ? (
            <div className="mt-4">
              <p className="font-mono text-sm text-accent">
                {snakePath.length ? snakePath.join(" → ") : "Start eating tokens…"}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(round.options || []).map((token) => (
                  <button
                    key={`${token}-${snakePath.length}`}
                    type="button"
                    disabled={locked}
                    onClick={() => eatToken(token)}
                    className="rounded-lg border border-muted/30 bg-bg px-3 py-1.5 font-mono text-sm"
                  >
                    {token}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="mt-3 text-sm text-muted"
                disabled={!snakePath.length || locked}
                onClick={() => setSnakePath([])}
              >
                Clear path
              </button>
            </div>
          ) : null}

          {game === "code_scramble" ? (
            <ul className="mt-4 space-y-2">
              {scrambleLines.map((line, index) => (
                <li
                  key={`${line.id}-${index}`}
                  className="flex items-stretch gap-2 rounded-xl border border-muted/20 bg-bg"
                >
                  <pre className="flex-1 overflow-x-auto px-3 py-2 font-mono text-sm">{line.text}</pre>
                  <div className="flex flex-col border-l border-muted/20">
                    <button
                      type="button"
                      className="px-2 py-1 text-xs text-muted disabled:opacity-30"
                      disabled={locked || index === 0}
                      onClick={() => moveScramble(index, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="px-2 py-1 text-xs text-muted disabled:opacity-30"
                      disabled={locked || index === scrambleLines.length - 1}
                      onClick={() => moveScramble(index, 1)}
                    >
                      ↓
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}

          {game === "predict_output" ||
          (game === "tic_tac_toe" && round.cell?.kind === "output") ||
          (game === "boss_battle" && round.mode === "output") ? (
            <div className="mt-4">
              <pre className="overflow-x-auto rounded-xl bg-bg px-4 py-3 font-mono text-sm">
                {round.code || round.cell?.code}
              </pre>
              <div className="mt-3 flex flex-col gap-2">
                {(round.choices || round.cell?.choices || []).map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    disabled={locked}
                    onClick={() =>
                      submit(choice, null, {
                        phase: game === "predict_output" ? "submit" : "choice",
                      })
                    }
                    className="rounded-xl border border-muted/30 bg-bg px-3 py-2 text-left font-mono text-sm hover:border-accent/50 disabled:opacity-50"
                  >
                    {choice || "(empty)"}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {game === "query_detective" ? (
            <div className="mt-4">
              <p className="text-xs uppercase tracking-wider text-muted">Result</p>
              <pre className="mt-2 overflow-x-auto rounded-xl bg-bg px-4 py-3 font-mono text-sm">
                {round.result}
              </pre>
            </div>
          ) : null}

          {game === "tic_tac_toe" ? (
            <div className="mt-4">
              <div className="mx-auto grid max-w-xs grid-cols-3 gap-2">
                {board.map((cell, index) => (
                  <div
                    key={index}
                    className="flex h-14 items-center justify-center rounded-xl border border-muted/30 font-mono text-lg"
                  >
                    {cell || "·"}
                  </div>
                ))}
              </div>
              {round.cell?.kind === "recall" ? (
                <p className="mt-3 text-sm text-muted">{round.cell.prompt}</p>
              ) : null}
            </div>
          ) : null}

          {game === "code_hangman" ||
          game === "codele" ||
          game === "memory_match" ||
          game === "syntax_snake" ||
          game === "predict_output" ||
          (game === "boss_battle" && round.mode === "output") ||
          (game === "tic_tac_toe" && round.cell?.kind === "output") ? null : (
            <div className="mt-4">
              {fillMode ? (
                <FillGap
                  code={round.code || round.scaffold || round.cell?.code || ""}
                  blanks={round.blanks || round.cell?.blanks || []}
                  values={blanks}
                  onChange={setBlanks}
                  disabled={locked}
                />
              ) : game === "code_scramble" || game === "code_crossword" ? null : (
                <GhostEditor
                  key={round.exercise_id}
                  value={draft}
                  onChange={setDraft}
                  target={game === "speed_drill" || game === "ghost_race" ? round.code : ""}
                  tokens={round.tokens || []}
                  disabled={locked}
                  onComplete={(stats) => submit(round.code, stats)}
                />
              )}
            </div>
          )}

          <HintsBlock
            round={round}
            hintsShown={hintsShown}
            setHintsShown={setHintsShown}
            reduce={reduce}
            locked={locked}
            onHintCost={
              game === "boss_battle"
                ? () => setBossHealth((hp) => Math.max(0, hp - 1))
                : undefined
            }
          />

          {expired ? <p className="mt-3 text-sm text-muted">Time is up — try again, or peek at the answer.</p> : null}
          {message ? <p className="mt-3 text-sm text-muted">{message}</p> : null}
          {revealedAnswer ? (
            <div className="mt-4 rounded-xl border border-accent/30 bg-bg/70 px-4 py-3">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                Answer
              </p>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-sm text-text">
                {revealedAnswer}
              </pre>
              <p className="mt-2 text-xs text-muted">
                Use Try again to type it yourself — XP is lower after a reveal.
              </p>
            </div>
          ) : null}
          {result?.passed ? (
            <div className="mt-4" role="status">
              <XpPop amount={result.xp_awarded} reduce={reduce} />
              <p className="text-success">Passed. {result.xp_total} XP total</p>
            </div>
          ) : null}

          <RoundActions
            game={game}
            pending={pending}
            locked={locked}
            result={result}
            expired={expired}
            stuck={stuck}
            count={count}
            maxRounds={maxRounds}
            revealedAnswer={revealedAnswer}
            hideCheck={
              game === "code_hangman" ||
              game === "codele" ||
              game === "memory_match" ||
              game === "syntax_snake" ||
              game === "predict_output" ||
              (game === "boss_battle" && round.mode === "output") ||
              (game === "tic_tac_toe" && round.cell?.kind === "output")
            }
            onCheck={() => {
              const cellIndex =
                game === "tic_tac_toe" ? board.findIndex((cell) => cell == null) : undefined;
              if (game === "code_crossword") {
                const answers = (round.clues || [])
                  .map((clue) => (crossword[clue.id] || "").trim())
                  .join("\n");
                submit(answers);
              } else if (game === "code_scramble") {
                submit(scrambleLines.map((line) => line.text).join("\n"));
              } else if (game === "syntax_snake") {
                submit(snakePath.join(" "));
              } else if (game === "tic_tac_toe") {
                submit(answer, null, {
                  cellIndex: cellIndex >= 0 ? cellIndex : 0,
                  phase: round.cell?.kind === "output" ? "choice" : "submit",
                });
              } else {
                submit(answer);
              }
            }}
            onNext={advanceOrFinish}
            onSkip={advanceOrFinish}
            onTryAgain={tryAgain}
            onSeeAnswer={seeAnswer}
            onEnd={() => setFinished(true)}
          />
        </>
      )}
    </SessionChrome>
  );
}
