import { useMemo, useState } from "react";

function shuffle(list) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Pick one token explanation and build a small multiple-choice question; null if not enough data. */
export function buildExplainQuestion(tokens) {
  const usable = (tokens || []).filter(
    (token) => String(token?.match || "").trim() && String(token?.explain || "").trim(),
  );
  const explains = [...new Set(usable.map((token) => String(token.explain).trim()))];
  if (usable.length < 2 || explains.length < 2) {
    return null;
  }
  const token = usable[Math.floor(Math.random() * usable.length)];
  const correct = String(token.explain).trim();
  const wrong = shuffle(explains.filter((item) => item !== correct)).slice(0, 2);
  return { match: String(token.match), correct, options: shuffle([correct, ...wrong]) };
}

/** After a pass, 30% of the time: "What does X do?" using the exercise's own token explanations. */
export function shouldExplainBack(tokens, chance = 0.3) {
  return Math.random() < chance && Boolean(buildExplainQuestion(tokens));
}

export default function ExplainBack({ tokens, id }) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const question = useMemo(() => buildExplainQuestion(tokens), [id]);
  const [picked, setPicked] = useState("");
  if (!question) {
    return null;
  }
  const answered = picked !== "";
  return (
    <fieldset className="mt-3 rounded-xl border border-muted/20 bg-bg/70 p-3">
      <legend className="px-1 text-sm font-medium text-text">
        Explain it back: what does <code className="font-mono">{question.match}</code> do?
      </legend>
      <div className="mt-2 flex flex-col gap-2">
        {question.options.map((option) => {
          const right = option === question.correct;
          return (
            <label
              key={option}
              className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm focus-within:outline focus-within:outline-2 focus-within:outline-accent ${
                answered && right
                  ? "border-success"
                  : answered && picked === option
                    ? "border-error"
                    : "border-muted/30"
              }`}
            >
              <input
                type="radio"
                name={`explain-${id}`}
                value={option}
                checked={picked === option}
                disabled={answered}
                onChange={() => setPicked(option)}
              />
              {option}
            </label>
          );
        })}
      </div>
      {answered ? (
        <p className="mt-2 text-sm text-muted" role="status">
          {picked === question.correct ? "Right." : `Not quite — it means: ${question.correct}`}
        </p>
      ) : null}
    </fieldset>
  );
}
