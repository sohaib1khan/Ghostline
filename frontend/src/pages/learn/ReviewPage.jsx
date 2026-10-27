import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import GhostEditor from "../../components/editor/GhostEditor.jsx";
import { indentUnitForTrack } from "../../components/editor/indent.js";
import { bumpDaily } from "../../lib/dailyGoal.js";
import { playSound } from "../../sounds.js";

const CONFIDENCE = [
  { id: "guessed", label: "Guessed" },
  { id: "unsure", label: "Unsure" },
  { id: "knew", label: "Knew it" },
];

export default function ReviewPage() {
  const [queue, setQueue] = useState([]);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [hintsShown, setHintsShown] = useState(0);
  const [confidence, setConfidence] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [passedCount, setPassedCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api("/api/review/due?limit=20");
        if (!cancelled) {
          setQueue(data.due || []);
          setLoading(false);
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(error.message || "Could not load reviews.");
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const item = queue[index];

  async function submit() {
    if (!item || pending) {
      return;
    }
    if (!confidence) {
      setMessage("Pick how sure you were first: Guessed, Unsure, or Knew it.");
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const result = await api(`/api/review/${item.id}`, {
        method: "POST",
        body: {
          attempt: draft,
          hints_used: hintsShown,
          confidence,
        },
      });
      if (result.passed) {
        playSound("correct");
        setPassedCount((count) => count + 1);
        bumpDaily("reviews");
        setMessage(`Passed. +${result.xp_awarded || 0} XP`);
        window.setTimeout(() => {
          setDraft("");
          setHintsShown(0);
          setConfidence("");
          setMessage("");
          setIndex((value) => value + 1);
        }, 700);
      } else {
        playSound("wrong");
        setMessage(result.failed_rule_hint || "Not quite — try a hint.");
        if (item.hints?.length && hintsShown < item.hints.length) {
          setHintsShown((count) => Math.min(count + 1, item.hints.length));
        }
      }
    } catch (error) {
      setMessage(error.message || "Check failed.");
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted">Loading reviews…</p>;
  }

  if (!queue.length || index >= queue.length) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold tracking-tight">Review today</h1>
        <p className="mt-3 text-muted" role="status">
          {passedCount
            ? `Nice work — you cleared ${passedCount} review${passedCount === 1 ? "" : "s"}.`
            : "Nothing is due right now. Keep learning and reviews will show up here."}
        </p>
        <Link to="/" className="mt-4 inline-flex text-accent">
          Back home
        </Link>
      </section>
    );
  }

  if (item.kind === "ghostwalk" || item.type === "ghostwalk") {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">
          {index + 1} of {queue.length} · Ghostwalk review
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{item.title}</h1>
        <p className="mt-2 text-sm text-muted">{item.concept}</p>
        <p className="mt-4">{item.prompt}</p>
        <Link
          to={`/ghostwalk/${item.slug}?memory=1`}
          className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent"
        >
          Open free replay
        </Link>
        <button
          type="button"
          className="mt-3 ml-3 min-h-11 text-sm text-accent"
          onClick={() => {
            setIndex((value) => value + 1);
            setMessage("");
          }}
        >
          Skip for now
        </button>
      </section>
    );
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">
        {index + 1} of {queue.length} · review
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Review today</h1>
      <p className="mt-2 text-sm text-muted">
        {item.track_name} · {item.module_title} · {item.lesson_title}
      </p>
      <p className="mt-4">{item.prompt}</p>
      <div className="mt-4">
        <GhostEditor
          key={item.id}
          value={draft}
          onChange={setDraft}
          ghost={hintsShown > 0 ? item.ghost || "" : ""}
          indentUnit={indentUnitForTrack(item.track_slug)}
          disabled={pending}
        />
      </div>
      {item.hints?.length ? (
        <div className="mt-4">
          <p className="text-xs text-muted">
            Stuck? Open a hint — it also turns on a typing ghost.
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {item.hints.slice(0, hintsShown).map((hint) => (
              <li key={hint} className="hint-card text-sm text-muted">
                {hint}
              </li>
            ))}
          </ul>
          {hintsShown < item.hints.length ? (
            <button
              type="button"
              className="mt-2 min-h-11 text-sm text-accent"
              onClick={() => setHintsShown((count) => count + 1)}
            >
              Hint ({hintsShown}/{item.hints.length})
              {hintsShown === 0 ? " · show ghost" : ""}
            </button>
          ) : null}
        </div>
      ) : null}
      <fieldset className="mt-4">
        <legend className="text-sm font-medium text-text">How sure were you?</legend>
        <p className="mt-1 text-xs text-muted">
          Pick one before Check. It helps schedule when this comes back.
        </p>
        <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Confidence">
          {CONFIDENCE.map((option) => (
            <label
              key={option.id}
              className={`inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-xl border px-4 py-2 text-sm focus-within:outline focus-within:outline-2 focus-within:outline-accent ${
                confidence === option.id
                  ? "border-accent bg-accent/15 font-medium text-text"
                  : "border-muted/30 text-muted"
              }`}
            >
              <input
                type="radio"
                name="review-confidence"
                value={option.id}
                className="sr-only"
                checked={confidence === option.id}
                disabled={pending}
                onChange={() => {
                  setConfidence(option.id);
                  setMessage("");
                }}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          className="min-h-11 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
          disabled={pending}
          onClick={submit}
        >
          {pending ? "Checking…" : "Check"}
        </button>
        <Link to="/" className="min-h-11 inline-flex items-center text-sm text-muted">
          Back
        </Link>
      </div>
      {message ? (
        <p className="mt-3 practice-check-fail" role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}
