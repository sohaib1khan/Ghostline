import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import MarkdownView from "../../components/content/MarkdownView.jsx";
import GhostEditor from "../../components/editor/GhostEditor.jsx";
import { playSound } from "../../sounds.js";

function formatWorth(worth) {
  return `${Math.round((worth || 0) * 100)}%`;
}

function formatCredit(credit) {
  const value = Number(credit || 0);
  const text = value.toFixed(2).replace(/\.?0+$/, "");
  return `+${text}`;
}

export default function BossPage() {
  const { moduleId } = useParams();
  const [boss, setBoss] = useState(null);
  const [runId, setRunId] = useState(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [openedHints, setOpenedHints] = useState([]);
  const [hintLevel, setHintLevel] = useState(0);
  const [itemEnded, setItemEnded] = useState(false);
  const [itemPassed, setItemPassed] = useState(false);
  const [itemCredit, setItemCredit] = useState(null);
  const [answer, setAnswer] = useState("");
  const [reviewLessonId, setReviewLessonId] = useState(null);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [finished, setFinished] = useState(null);
  const [error, setError] = useState("");

  async function beginRun() {
    setError("");
    setFinished(null);
    setIndex(0);
    setDraft("");
    setOpenedHints([]);
    setHintLevel(0);
    setItemEnded(false);
    setItemPassed(false);
    setItemCredit(null);
    setAnswer("");
    setReviewLessonId(null);
    setMessage("");
    const data = await api(`/api/learn/modules/${moduleId}/boss/start`, { method: "POST" });
    setBoss(data);
    setRunId(data.run_id);
  }

  useEffect(() => {
    let cancelled = false;
    beginRun().catch((err) => {
      if (!cancelled) {
        setError(err.message);
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moduleId]);

  const item = boss?.items?.[index];
  const total = boss?.count || boss?.items?.length || 0;

  function resetItemLocal() {
    setDraft("");
    setOpenedHints([]);
    setHintLevel(0);
    setItemEnded(false);
    setItemPassed(false);
    setItemCredit(null);
    setAnswer("");
    setReviewLessonId(null);
    setMessage("");
  }

  async function openHint(level) {
    if (!item || !runId || pending || itemEnded) {
      return;
    }
    if (level !== hintLevel + 1) {
      return;
    }
    setPending(true);
    try {
      const result = await api(`/api/learn/modules/${moduleId}/boss/${runId}/hint`, {
        method: "POST",
        body: { exercise_id: item.id, level },
      });
      setHintLevel(result.hint_level || level);
      setOpenedHints((prev) => [...prev, { level, text: result.text || "" }]);
    } catch (err) {
      setMessage(err.message || "Could not open hint.");
    } finally {
      setPending(false);
    }
  }

  async function submit() {
    if (!item || !runId || pending || itemEnded) {
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const outcome = await api(`/api/learn/modules/${moduleId}/boss/${runId}/check`, {
        method: "POST",
        body: { exercise_id: item.id, attempt: draft },
      });
      setMessage(outcome.message || "");
      if (outcome.passed) {
        playSound("correct");
        setItemPassed(true);
        setItemCredit(outcome.credit);
        setItemEnded(true);
        setAnswer(outcome.answer || "");
      } else if (outcome.ended) {
        playSound("wrong");
        setItemPassed(false);
        setItemCredit(0);
        setItemEnded(true);
        setAnswer(outcome.answer || "");
        setReviewLessonId(outcome.lesson_id || item.lesson_id || null);
      } else {
        playSound("wrong");
      }
    } catch (err) {
      setMessage(err.message || "Check failed.");
    } finally {
      setPending(false);
    }
  }

  async function reveal() {
    if (!item || !runId || pending || itemEnded) {
      return;
    }
    if (
      !window.confirm(
        "Show the answer? This item will score 0.",
      )
    ) {
      return;
    }
    setPending(true);
    try {
      const outcome = await api(`/api/learn/modules/${moduleId}/boss/${runId}/reveal`, {
        method: "POST",
        body: { exercise_id: item.id },
      });
      playSound("wrong");
      setMessage(outcome.message || "Answer revealed.");
      setItemPassed(false);
      setItemCredit(0);
      setItemEnded(true);
      setAnswer(outcome.answer || "");
      setReviewLessonId(outcome.lesson_id || item.lesson_id || null);
    } catch (err) {
      setMessage(err.message || "Could not reveal.");
    } finally {
      setPending(false);
    }
  }

  async function goNext() {
    if (pending) {
      return;
    }
    if (index + 1 >= total) {
      setPending(true);
      try {
        const summary = await api(`/api/learn/modules/${moduleId}/boss/${runId}/finish`, {
          method: "POST",
        });
        setFinished(summary);
      } catch (err) {
        setMessage(err.message || "Could not finish boss.");
      } finally {
        setPending(false);
      }
      return;
    }
    setIndex((value) => value + 1);
    resetItemLocal();
  }

  if (error) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold">Module boss</h1>
        <p className="mt-3 text-sm text-error" role="status">
          {error}
        </p>
        <Link to="/" className="mt-4 inline-flex min-h-11 items-center text-accent">
          Back home
        </Link>
      </section>
    );
  }

  if (!boss) {
    return <p className="text-sm text-muted">Loading boss…</p>;
  }

  if (finished) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold">{boss.module_title} · Boss</h1>
        <p className="mt-3 text-muted" role="status" aria-live="polite">
          {finished.mastered
            ? `Mastered — score ${finished.score}% (pass mark ${finished.pass_mark}%).`
            : `Score ${finished.score}% — need ${finished.pass_mark}% to master. Try again.`}
        </p>
        {finished.mastered_without_hints ? (
          <p className="mt-2 text-sm font-medium text-success">Mastered without hints</p>
        ) : null}
        <ul className="mt-4 flex flex-col gap-2" aria-label="Boss item results">
          {(finished.items || []).map((entry, i) => (
            <li
              key={entry.exercise_id || i}
              className="rounded-xl border border-muted/20 px-3 py-2 text-sm"
            >
              <span className="font-medium">
                {entry.passed ? "✓ Pass" : "✗ Miss"} · Item {i + 1}
              </span>
              <span className="text-muted">
                {" "}
                · hints {entry.hint_level || 0} · credit {Number(entry.credit || 0).toFixed(2)}
              </span>
              {entry.mastered_without_hints ? (
                <span className="ml-2 text-success">Mastered without hints</span>
              ) : null}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent"
            onClick={() => {
              beginRun().catch((err) => setError(err.message));
            }}
          >
            Retry boss
          </button>
          <Link to="/" className="inline-flex min-h-11 items-center text-accent">
            Home
          </Link>
        </div>
      </section>
    );
  }

  if (!boss.items?.length) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold">{boss.module_title}</h1>
        <p className="mt-3 text-muted">This module does not have enough recall items for a boss yet.</p>
      </section>
    );
  }

  const costs = item?.hint_costs || [];

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">Module boss</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{boss.module_title}</h1>
      <p className="mt-2 text-sm text-muted">
        Hints cost points. Pass mark {Math.round((boss.pass_mark || 0.7) * 100)}%. Item{" "}
        {index + 1} of {total}.
      </p>
      <p className="mt-4 text-base text-text">{item.prompt}</p>

      <div className="mt-4">
        <p className="text-sm font-medium">Need a nudge?</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {costs.map((cost) => {
            const opened = hintLevel >= cost.level;
            const next = cost.level === hintLevel + 1;
            return (
              <button
                key={cost.level}
                type="button"
                className="inline-flex min-h-11 items-center rounded-xl border border-muted/30 px-3 text-sm disabled:opacity-50"
                disabled={pending || itemEnded || opened || !next}
                onClick={() => openHint(cost.level)}
              >
                {cost.label} (item worth {formatWorth(cost.worth)})
              </button>
            );
          })}
          {costs.length === 0 ? (
            <p className="text-sm text-muted">No authored hints for this item.</p>
          ) : null}
        </div>
      </div>

      {openedHints.length ? (
        <div className="mt-4 flex flex-col gap-3" aria-live="polite">
          {openedHints.map((hint) => (
            <div key={hint.level} className="rounded-xl border border-muted/20 bg-bg/40 p-3">
              <p className="mb-1 text-xs font-mono uppercase tracking-[0.14em] text-muted">
                Hint {hint.level}
              </p>
              <MarkdownView text={hint.text} />
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-4">
        <GhostEditor value={draft} onChange={setDraft} ghost="" disabled={pending || itemEnded} />
      </div>

      <div className="mt-3 min-h-11" aria-live="polite" role="status">
        {message ? <p className="text-sm text-muted">{message}</p> : null}
        {itemEnded && itemPassed ? (
          <p className="mt-1 text-sm font-medium text-success">
            Correct {itemCredit != null ? formatCredit(itemCredit) : ""}
          </p>
        ) : null}
        {itemEnded && !itemPassed && answer ? (
          <div className="mt-2">
            <p className="text-sm font-medium">Right answer</p>
            <pre className="mt-1 overflow-x-auto rounded-xl bg-bg p-3 font-mono text-sm">{answer}</pre>
            {reviewLessonId ? (
              <Link
                to={`/learn/lessons/${reviewLessonId}`}
                className="mt-2 inline-flex min-h-11 items-center text-sm text-accent"
              >
                Review this lesson
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!itemEnded ? (
          <>
            <button
              type="button"
              className="inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent disabled:opacity-60"
              disabled={pending}
              onClick={submit}
            >
              Check
            </button>
            <button
              type="button"
              className="inline-flex min-h-11 items-center text-sm text-muted underline-offset-2 hover:underline disabled:opacity-60"
              disabled={pending}
              onClick={reveal}
            >
              Show answer
            </button>
          </>
        ) : (
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent disabled:opacity-60"
            disabled={pending}
            onClick={goNext}
          >
            {index + 1 >= total ? "See results" : "Next"}
          </button>
        )}
      </div>
    </section>
  );
}
