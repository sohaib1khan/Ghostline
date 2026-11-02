import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client.js";
import {
  markSeen,
  optionsForItem,
  pickQuizQuestion,
  quizQuestionId,
} from "./quizSelect.js";

function poolFromLesson(exercise, lessonExercises) {
  const rows = [];
  const currentId = exercise?.id;
  for (const item of exercise?.quiz || []) {
    rows.push({ exerciseId: currentId, item });
  }
  for (const other of lessonExercises || []) {
    if (!other?.id || other.id === currentId) continue;
    for (const item of other.quiz || []) {
      rows.push({ exerciseId: other.id, item });
    }
  }
  return rows;
}

function CodeBlock({ code }) {
  const lines = String(code || "").replace(/\n$/, "").split("\n");
  return (
    <pre
      className="mt-3 max-h-64 overflow-auto rounded-xl border border-muted/20 bg-bg p-3 font-mono text-sm leading-relaxed"
      tabIndex={0}
      aria-label="Quiz code"
    >
      <code className="block whitespace-pre">
        {lines.map((line, index) => (
          <span key={`${index}-${line}`} className="block">
            <span className="mr-3 inline-block w-6 select-none text-right text-muted">
              {index + 1}
            </span>
            {line || " "}
          </span>
        ))}
      </code>
    </pre>
  );
}

export default function QuizCheck({ exercise, lessonExercises = [], accountXp = true, onXp }) {
  const pool = useMemo(
    () => poolFromLesson(exercise, lessonExercises),
    [exercise, lessonExercises],
  );
  const [current, setCurrent] = useState(null);
  const [options, setOptions] = useState([]);
  const [picked, setPicked] = useState("");
  const [status, setStatus] = useState("");
  const [xpNote, setXpNote] = useState("");
  const [firstTry, setFirstTry] = useState(true);
  const [skipped, setSkipped] = useState(false);

  function loadNext(lastId = null) {
    const next = pickQuizQuestion(pool, { lastId });
    if (!next) {
      setCurrent(null);
      return;
    }
    markSeen(next.id);
    setCurrent(next);
    setOptions(optionsForItem(next.item));
    setPicked("");
    setStatus("");
    setXpNote("");
    setFirstTry(true);
    setSkipped(false);
  }

  useEffect(() => {
    loadNext(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exercise?.id, pool.length]);

  if (skipped || !current) {
    return null;
  }

  const item = current.item;
  const answered = picked !== "";
  const correct = String(item.answer ?? "");
  const kindLabel = item.kind === "output" ? "Predict the output" : "Check your understanding";
  const name = `quiz-${quizQuestionId(current.exerciseId, item)}`;

  async function choose(option) {
    if (answered) return;
    setPicked(option);
    const right = option === correct;
    setStatus(right ? "Right." : `Not quite. The answer is ${correct}`);
    try {
      const data = await api(`/api/exercises/${current.exerciseId}/quiz/result`, {
        method: "POST",
        body: {
          q: item.q,
          code: item.code || "",
          picked: option,
          first_try: firstTry && right,
        },
      });
      if (data.xp_awarded > 0) {
        setXpNote(`+${data.xp_awarded} XP`);
        if (accountXp && onXp) onXp(data.xp_awarded);
      }
    } catch {
      // Keep local feedback even if the soft log fails.
    }
    if (!right) {
      setFirstTry(false);
    }
  }

  return (
    <section className="mt-3 rounded-xl border border-muted/20 bg-bg/70 p-3" aria-label="Quiz">
      <p className="inline-block rounded-lg border border-muted/30 px-2 py-1 text-xs font-medium text-muted">
        {kindLabel}
      </p>
      <h3 className="mt-3 text-base font-medium text-text">{item.q}</h3>
      {item.code ? <CodeBlock code={item.code} /> : null}
      <fieldset className="mt-3">
        <legend className="sr-only">Choose an answer</legend>
        <div className="flex flex-col gap-2" role="radiogroup" aria-label="Answers">
          {options.map((option) => {
            const right = option === correct;
            const chosen = picked === option;
            let border = "border-muted/30";
            if (answered && right) border = "border-success";
            else if (answered && chosen) border = "border-error";
            return (
              <label
                key={option}
                className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border px-3 py-2 focus-within:outline focus-within:outline-2 focus-within:outline-accent ${border}`}
              >
                <input
                  type="radio"
                  className="mt-1"
                  name={name}
                  value={option}
                  checked={chosen}
                  disabled={answered}
                  onChange={() => choose(option)}
                />
                <pre className="m-0 flex-1 whitespace-pre-wrap break-words font-mono text-sm leading-relaxed">
                  {option}
                </pre>
              </label>
            );
          })}
        </div>
      </fieldset>
      {answered ? (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-muted" role="status" aria-live="polite">
            {status}
            {xpNote ? ` ${xpNote}` : ""}
          </p>
          {item.why ? <p className="text-sm text-text">{item.why}</p> : null}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="min-h-11 rounded-xl bg-accent px-4 text-sm font-medium text-white"
              onClick={() => setSkipped(true)}
            >
              Continue
            </button>
            <button
              type="button"
              className="min-h-11 rounded-xl border border-muted/30 px-4 text-sm"
              onClick={() => loadNext(current.id)}
            >
              Another question
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="mt-3 min-h-11 text-sm text-muted underline"
          onClick={() => setSkipped(true)}
        >
          Skip
        </button>
      )}
    </section>
  );
}
