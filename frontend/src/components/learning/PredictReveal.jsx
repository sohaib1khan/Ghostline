import { useState } from "react";

/** Ask what output will be, then reveal the expected value side by side. */
export default function PredictReveal({ expected = "", choices = null, onDone }) {
  const [guess, setGuess] = useState("");
  const [choice, setChoice] = useState("");
  const [revealed, setRevealed] = useState(false);

  function reveal() {
    setRevealed(true);
    onDone?.(choices ? choice : guess);
  }

  return (
    <div className="rounded-xl border border-muted/25 p-4">
      <h2 className="text-lg font-semibold">What will this print?</h2>
      {!revealed ? (
        <>
          {choices?.length ? (
            <div className="mt-3 flex flex-col gap-2" role="radiogroup" aria-label="Predicted output">
              {choices.map((item) => (
                <button
                  key={item}
                  type="button"
                  role="radio"
                  aria-checked={choice === item}
                  className={`min-h-11 rounded-xl border px-3 text-left text-sm ${
                    choice === item ? "border-accent bg-accent/15" : "border-muted/30"
                  }`}
                  onClick={() => setChoice(item)}
                >
                  <code>{item}</code>
                </button>
              ))}
            </div>
          ) : (
            <label className="mt-3 block text-sm">
              Your prediction
              <textarea
                className="mt-1 min-h-24 w-full rounded-xl border border-muted/30 bg-bg p-3 font-mono text-sm"
                value={guess}
                onChange={(event) => setGuess(event.target.value)}
              />
            </label>
          )}
          <button
            type="button"
            className="mt-3 inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent disabled:opacity-50"
            disabled={choices ? !choice : !guess.trim()}
            onClick={reveal}
          >
            Reveal
          </button>
        </>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-wider text-muted">Your guess</p>
            <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-bg p-3 font-mono text-sm">
              {choices ? choice : guess}
            </pre>
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase tracking-wider text-muted">Actual</p>
            <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-bg p-3 font-mono text-sm">
              {expected}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
