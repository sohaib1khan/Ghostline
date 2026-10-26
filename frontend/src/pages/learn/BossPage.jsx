import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import GhostEditor from "../../components/editor/GhostEditor.jsx";
import { playSound } from "../../sounds.js";

export default function BossPage() {
  const { moduleId } = useParams();
  const [boss, setBoss] = useState(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [results, setResults] = useState([]);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [finished, setFinished] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`/api/learn/modules/${moduleId}/boss`)
      .then((data) => {
        if (!cancelled) {
          setBoss(data);
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
  }, [moduleId]);

  const item = boss?.items?.[index];

  async function submit() {
    if (!item || pending) {
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const outcome = await api(`/api/check/${item.id}`, {
        method: "POST",
        body: {
          attempt: draft,
          hints_used: 0,
        },
      });
      const nextResults = [...results, { exercise_id: item.id, passed: !!outcome.passed }];
      setResults(nextResults);
      if (outcome.passed) {
        playSound("correct");
        setMessage("Correct.");
      } else {
        playSound("wrong");
        setMessage(outcome.failed_rule_hint || "Not quite.");
      }
      window.setTimeout(async () => {
        setDraft("");
        setMessage("");
        if (index + 1 >= (boss.items?.length || 0)) {
          const summary = await api(`/api/learn/modules/${moduleId}/boss`, {
            method: "POST",
            body: { results: nextResults },
          });
          setFinished(summary);
        } else {
          setIndex((value) => value + 1);
        }
      }, 500);
    } catch (err) {
      setMessage(err.message || "Check failed.");
    } finally {
      setPending(false);
    }
  }

  if (error) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold">Module boss</h1>
        <p className="mt-3 text-sm text-error" role="status">
          {error}
        </p>
        <Link to="/" className="mt-4 inline-flex text-accent">
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
        <p className="mt-3 text-muted" role="status">
          {finished.mastered
            ? `Mastered — score ${finished.score}% (pass mark ${finished.pass_mark}%).`
            : `Score ${finished.score}% — need ${finished.pass_mark}% to master. Try again.`}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent"
            onClick={() => {
              setFinished(null);
              setIndex(0);
              setResults([]);
              setDraft("");
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

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">Module boss</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{boss.module_title}</h1>
      <p className="mt-2 text-sm text-muted">
        No hints. Pass mark {Math.round((boss.pass_mark || 0.7) * 100)}%. Item {index + 1} of{" "}
        {boss.count}.
      </p>
      <p className="mt-4 text-base text-text">{item.prompt}</p>
      <div className="mt-4">
        <GhostEditor value={draft} onChange={setDraft} ghost="" disabled={pending} />
      </div>
      {message ? (
        <p className="mt-3 text-sm text-muted" role="status">
          {message}
        </p>
      ) : null}
      <button
        type="button"
        className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent disabled:opacity-60"
        disabled={pending}
        onClick={submit}
      >
        Check
      </button>
    </section>
  );
}
