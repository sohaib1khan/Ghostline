import { useEffect, useMemo, useRef, useState } from "react";
import { recordWalkthrough } from "./sandbox.js";
import { readPrefs } from "../../prefs.js";

function setupChips(setup) {
  return String(setup || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseChanged(prev, next) {
  const was = prev || {};
  const now = next || {};
  const names = [...new Set([...Object.keys(was), ...Object.keys(now)])].sort();
  return names.map((name) => {
    const before = was[name];
    const after = now[name];
    const isNew = before === undefined && after !== undefined;
    const changed = !isNew && before !== after;
    return { name, before, after, isNew, changed };
  });
}

function specialNote(step, expectError) {
  if (!step) return null;
  if (step.event === "return") {
    const name = step.frames?.length
      ? step.frames[step.frames.length - 1]?.name || "function"
      : "function";
    return `\`${name}\` hands back \`${step.returned}\``;
  }
  if (step.event === "yield") {
    const name = step.frames?.length
      ? step.frames[step.frames.length - 1]?.name || "generator"
      : "generator";
    return `\`${name}\` pauses and hands out \`${step.returned}\``;
  }
  if (step.event === "exception" || step.error) {
    const text = step.error || "An error stopped the program.";
    const expected =
      expectError && String(text).startsWith(String(expectError))
        ? " This error is the point of the example."
        : "";
    return { kind: "error", text: `${text}${expected}` };
  }
  return null;
}

function VarTable({ rows }) {
  if (!rows.length) {
    return <p className="text-sm text-muted">No variables yet.</p>;
  }
  return (
    <table className="w-full border-collapse text-left text-base">
      <thead>
        <tr className="text-sm text-muted">
          <th className="py-1 pr-3 font-medium">Name</th>
          <th className="py-1 font-medium">Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.name}
            className={
              row.changed || row.isNew
                ? "bg-[color-mix(in_srgb,var(--accent)_18%,transparent)]"
                : undefined
            }
          >
            <td className="py-2 pr-3 align-top font-mono text-sm">
              {row.name}
              {row.isNew ? (
                <span className="ml-2 rounded bg-accent/20 px-1.5 py-0.5 text-xs text-accent">
                  new
                </span>
              ) : null}
            </td>
            <td className="py-2 align-top font-mono text-sm break-all">
              {row.changed ? (
                <span>
                  <span className="text-muted">{row.before}</span>
                  {" → "}
                  <span className="font-semibold">{row.after}</span>
                </span>
              ) : (
                row.after ?? "—"
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Thonny-style step-through viewer.
 * @param {{ walk: object, onClose?: () => void, exerciseId?: string }} props
 */
export default function StepThrough({ walk, onClose = null, exerciseId = null }) {
  const prefs = readPrefs();
  const reduce = prefs.reduceMotion;
  const notesOnly = walk?.run === false;
  const [recording, setRecording] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!notesOnly);
  const [index, setIndex] = useState(0);
  const [predictOff] = useState(() => prefs.predictValues === false);
  const [predictAnswer, setPredictAnswer] = useState("");
  const [predictRevealed, setPredictRevealed] = useState({});
  const [predictAsked, setPredictAsked] = useState(0);
  const codeRef = useRef(null);
  const panelRef = useRef(null);

  const lines = useMemo(
    () => String(walk?.program || "").replace(/\n$/, "").split("\n"),
    [walk?.program],
  );
  const sourceLines = Number(walk?.source_lines || lines.length);
  const notes = walk?.notes || {};

  useEffect(() => {
    if (notesOnly) {
      setRecording({ steps: lines.map((_, i) => ({ line: i + 1, event: "line", globals: {}, frames: [], stdout_len: 0 })), stdout: "", error: null, truncated: false });
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    recordWalkthrough({
      program: walk.program,
      setup: walk.setup,
      stdin: walk.stdin,
    })
      .then((result) => {
        if (!cancelled) {
          setRecording(result);
          setIndex(0);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || "Could not record the walkthrough.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [walk, notesOnly, lines]);

  const steps = recording?.steps || [];
  const step = steps[index] || null;
  const prev = steps[index - 1] || null;
  const total = steps.length;

  useEffect(() => {
    if (!codeRef.current || !step?.line) return;
    const row = codeRef.current.querySelector(`[data-line="${step.line}"]`);
    row?.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [step?.line, reduce]);

  const seenLines = useMemo(() => {
    const counts = {};
    for (let i = 0; i <= index; i += 1) {
      const line = steps[i]?.line;
      if (line) counts[line] = (counts[line] || 0) + 1;
    }
    return counts;
  }, [steps, index]);

  const loopNote =
    step?.event === "line" && step.line && (seenLines[step.line] || 0) > 1
      ? `Back to line ${step.line}: the next round of the loop.`
      : null;

  const noteText = notes[step?.line] || notes[String(step?.line)] || "";
  const special = specialNote(step, walk?.expect_error);

  const globalRows = useMemo(
    () => parseChanged(prev?.globals, step?.globals).filter((row) => row.after !== undefined),
    [prev, step],
  );

  const stdout = String(recording?.stdout || "");
  const shownOut = step ? stdout.slice(0, step.stdout_len || 0) : "";
  const prevOut = prev ? stdout.slice(0, prev.stdout_len || 0) : "";
  const newOut = shownOut.slice(prevOut.length);

  const predictTarget = useMemo(() => {
    if (notesOnly || predictOff || predictAsked >= 2 || !step || step.event !== "line") {
      return null;
    }
    if (predictRevealed[index]) return null;
    const changed = parseChanged(prev?.globals, step?.globals).filter(
      (row) => row.changed && row.after !== undefined,
    );
    return changed[0] || null;
  }, [notesOnly, predictOff, predictAsked, step, prev, predictRevealed, index]);

  function go(nextIndex) {
    setIndex(Math.max(0, Math.min(total - 1, nextIndex)));
    setPredictAnswer("");
  }

  function revealPredict() {
    if (!predictTarget) return;
    setPredictRevealed((current) => ({ ...current, [index]: true }));
    setPredictAsked((count) => count + 1);
    const ok = String(predictAnswer).trim() === String(predictTarget.after).trim();
    if (!ok && exerciseId) {
      import("../../api/client.js")
        .then(({ api }) =>
          api(`/api/exercises/${exerciseId}/walkthrough/predict-miss`, {
            method: "POST",
            body: {
              name: predictTarget.name,
              guessed: predictAnswer,
              expected: String(predictTarget.after),
            },
          }).catch(() => null),
        )
        .catch(() => null);
    }
  }

  useEffect(() => {
    const node = panelRef.current;
    if (!node) return undefined;
    function onKey(event) {
      if (!node.contains(document.activeElement) && document.activeElement !== node) {
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        go(index + 1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        go(index - 1);
      } else if (event.key === "Home") {
        event.preventDefault();
        go(0);
      } else if (event.key === "End") {
        event.preventDefault();
        go(total - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const chips = setupChips(walk?.setup);

  return (
    <section
      ref={panelRef}
      tabIndex={0}
      className="step-through rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_22%,transparent)] bg-surface p-4 shadow-[var(--shadow)] outline-none sm:p-6"
      aria-label="Step through"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            {notesOnly ? "Read line by line" : "Step through"}
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">
            Watch the program one line at a time
          </h2>
        </div>
        {onClose ? (
          <button type="button" className="min-h-11 rounded-xl border border-muted/30 px-4 text-sm" onClick={onClose}>
            Close
          </button>
        ) : null}
      </div>

      {chips.length ? (
        <div className="mt-4" aria-label="Values given before the program">
          <p className="text-sm font-medium text-muted">Given</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {chips.map((chip) => (
              <li
                key={chip}
                className="rounded-full border border-muted/30 bg-bg px-3 py-2 font-mono text-sm"
              >
                {chip}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {loading ? <p className="mt-4 text-base text-muted">Recording steps…</p> : null}
      {error ? <p className="mt-4 text-base text-error">{error}</p> : null}

      {!loading && !error ? (
        <>
          <div
            ref={codeRef}
            className="mt-4 max-h-[min(40vh,22rem)] overflow-auto rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_20%,transparent)] bg-bg p-3 font-mono text-base leading-relaxed"
            aria-label="Program"
          >
            {lines.map((text, i) => {
              const lineNo = i + 1;
              const active = step?.line === lineNo;
              const added = lineNo > sourceLines;
              return (
                <div
                  key={`L${lineNo}`}
                  data-line={lineNo}
                  className={[
                    "flex gap-3 rounded-lg px-2 py-1",
                    active
                      ? "bg-[color-mix(in_srgb,var(--accent)_22%,transparent)] ring-2 ring-accent"
                      : "",
                  ].join(" ")}
                >
                  <span className="w-8 shrink-0 text-right text-muted" aria-hidden="true">
                    {active ? "▶" : lineNo}
                  </span>
                  <span className="min-w-0 flex-1 whitespace-pre-wrap break-all">
                    {text || " "}
                    {added ? (
                      <span className="ml-2 text-xs text-muted">added so you can watch it run</span>
                    ) : null}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="mt-4 rounded-xl border-2 border-accent/30 bg-bg/60 p-4" aria-live="polite">
            <p className="text-lg font-medium leading-relaxed text-text">
              {noteText || "Watch what this line does."}
            </p>
            {loopNote ? <p className="mt-2 text-base text-muted">{loopNote}</p> : null}
            {special ? (
              typeof special === "string" ? (
                <p className="mt-2 text-base text-accent">{special}</p>
              ) : (
                <p className="mt-2 rounded-lg bg-error/15 p-3 text-base text-error">{special.text}</p>
              )
            ) : null}
          </div>

          {!notesOnly ? (
            <>
              <div className="mt-4 grid gap-4 min-[900px]:grid-cols-2">
                <div className="rounded-xl border border-muted/25 bg-bg/50 p-4">
                  <h3 className="text-base font-semibold">Variables</h3>
                  {predictTarget && !predictRevealed[index] ? (
                    <div className="mt-3 rounded-lg border border-accent/40 p-3">
                      <p className="text-base">
                        What will <code className="font-mono text-accent">{predictTarget.name}</code>{" "}
                        be after this line?
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <input
                          className="min-h-11 min-w-[8rem] flex-1 rounded-xl border border-muted/30 bg-surface px-3 font-mono"
                          value={predictAnswer}
                          onChange={(event) => setPredictAnswer(event.target.value)}
                          aria-label={`Predict ${predictTarget.name}`}
                        />
                        <button
                          type="button"
                          className="min-h-11 rounded-xl bg-accent px-4 text-sm font-medium text-on-accent"
                          onClick={revealPredict}
                        >
                          Reveal
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <div className="mt-3">
                    <VarTable
                      rows={
                        predictTarget && !predictRevealed[index]
                          ? globalRows.map((row) =>
                              row.name === predictTarget.name
                                ? { ...row, after: "?", changed: false }
                                : row,
                            )
                          : globalRows
                      }
                    />
                  </div>
                  {(step?.frames || []).map((frame) => (
                    <div
                      key={`${frame.name}-${JSON.stringify(frame.vars)}`}
                      className="mt-4 rounded-lg border border-muted/30 bg-surface/80 p-3"
                    >
                      <p className="mb-2 text-sm font-semibold text-accent">
                        Inside `{frame.name}()`
                      </p>
                      <VarTable
                        rows={Object.keys(frame.vars || {})
                          .sort()
                          .map((name) => ({
                            name,
                            after: frame.vars[name],
                            before: undefined,
                            isNew: false,
                            changed: false,
                          }))}
                      />
                    </div>
                  ))}
                </div>
                <div className="rounded-xl border border-muted/25 bg-bg/50 p-4">
                  <h3 className="text-base font-semibold">Output</h3>
                  <pre
                    className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap break-all font-mono text-sm leading-relaxed"
                    aria-live="polite"
                  >
                    <span>{prevOut}</span>
                    {newOut ? (
                      <span className="bg-[color-mix(in_srgb,var(--accent)_25%,transparent)]">
                        {newOut}
                      </span>
                    ) : null}
                    {!shownOut ? <span className="text-muted">(no output yet)</span> : null}
                  </pre>
                </div>
              </div>
              {recording?.truncated ? (
                <p className="mt-3 text-sm text-muted" role="status">
                  Stopped after 600 steps. That is enough to see the pattern.
                </p>
              ) : null}
            </>
          ) : null}

          <div
            className="mt-5 flex flex-wrap items-center gap-2"
            role="group"
            aria-label="Step controls"
          >
            <button
              type="button"
              className="min-h-11 rounded-xl border-2 border-muted/30 px-4 text-base"
              onClick={() => go(0)}
              disabled={index === 0}
            >
              ⏮ Start
            </button>
            <button
              type="button"
              className="min-h-11 rounded-xl border-2 border-muted/30 px-4 text-base"
              onClick={() => go(index - 1)}
              disabled={index === 0}
            >
              ◀ Back
            </button>
            <button
              type="button"
              className="min-h-11 rounded-xl bg-accent px-5 text-base font-semibold text-on-accent disabled:opacity-50"
              onClick={() => go(index + 1)}
              disabled={index >= total - 1}
            >
              Step ▶
            </button>
            <button
              type="button"
              className="min-h-11 rounded-xl border-2 border-muted/30 px-4 text-base"
              onClick={() => go(total - 1)}
              disabled={index >= total - 1}
            >
              ⏭ Run to end
            </button>
            <p className="ml-auto font-mono text-sm text-muted" role="status">
              Step {total ? index + 1 : 0} of {total}
            </p>
          </div>
        </>
      ) : null}
    </section>
  );
}
