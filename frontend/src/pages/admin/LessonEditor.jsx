import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import MarkdownView from "../../components/content/MarkdownView.jsx";

const StepThrough = lazy(() => import("../../components/editor/StepThrough.jsx"));

const TYPES = ["trace", "fill", "recall", "challenge"];
const RUNTIMES = ["none", "browser_js", "pyodide"];
const KINDS = [
  "exact",
  "must_contain",
  "must_not_contain",
  "must_contain_any",
  "must_contain_all",
  "regex",
  "line_count",
  "output_equals",
];

function blankWalkthrough() {
  return {
    setup: "",
    stdinText: "",
    try_it: "",
    run: true,
    expect_error: "",
    notes: {},
  };
}

function blankQuizItem() {
  return {
    kind: "concept",
    q: "",
    code: "",
    answer: "",
    wrongText: "",
    why: "",
  };
}

function blankExercise(type = "recall") {
  return {
    type,
    prompt: "",
    runtime: "none",
    code: "",
    tokens: [],
    blanks: type === "fill" ? [{ index: 1, placeholder: "____" }] : [],
    check: {
      mode: "either",
      accepted_answers: [],
      normalize: {
        collapse_whitespace: true,
        trim: true,
        equivalent_quotes: false,
        case_sensitive: true,
        indent_levels: false,
        comma_space: false,
      },
      rules: [],
    },
    hints: [],
    simulated_output: "",
    expected_output: "",
    xp: 10,
    time_limit_seconds: null,
    walkthroughForm: blankWalkthrough(),
    walkthroughEnabled: false,
    quizForm: [],
  };
}

function lines(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function programFromForm(form) {
  const source = String(form.code || "").trim()
    ? String(form.code || "").replace(/\n+$/, "")
    : lines(form.answersText || "")[0] || "";
  const tryIt = form.walkthroughForm?.try_it || "";
  return source.replace(/\n+$/, "") + (tryIt.trim() ? `\n\n${tryIt.replace(/^\n+/, "")}` : "");
}

function payloadFromForm(form) {
  const data = {
    ...form,
    hints: lines(form.hintsText || ""),
    simulated_output: form.simulated_output || null,
    expected_output: form.expected_output || null,
    time_limit_seconds:
      form.type === "challenge"
        ? form.time_limit_seconds === "" || form.time_limit_seconds == null
          ? null
          : Number(form.time_limit_seconds)
        : null,
    xp: Number(form.xp || 0),
    check: {
      ...form.check,
      accepted_answers: lines(form.answersText || ""),
      rules: form.check.rules.map((rule) => ({
        kind: rule.kind,
        value: rule.value || null,
        values: rule.valuesText ? lines(rule.valuesText) : [],
        pattern: rule.pattern || null,
        hint: rule.hint || "",
        minimum: rule.minimum === "" || rule.minimum == null ? null : Number(rule.minimum),
        maximum: rule.maximum === "" || rule.maximum == null ? null : Number(rule.maximum),
      })),
    },
  };
  if (form.walkthroughEnabled) {
    const notes = {};
    for (const [key, value] of Object.entries(form.walkthroughForm?.notes || {})) {
      const text = String(value || "").trim();
      if (text) notes[Number(key)] = text;
    }
    data.walkthrough = {
      setup: form.walkthroughForm?.setup || "",
      stdin: lines(form.walkthroughForm?.stdinText || ""),
      try_it: form.walkthroughForm?.try_it || "",
      run: form.walkthroughForm?.run !== false,
      expect_error: form.walkthroughForm?.expect_error || null,
      notes,
    };
  } else {
    data.walkthrough = null;
  }
  data.quiz = (form.quizForm || [])
    .filter((item) => String(item.q || "").trim() && String(item.answer || "").trim())
    .map((item) => ({
      kind: item.kind === "output" ? "output" : "concept",
      q: String(item.q || "").trim(),
      code: item.code || "",
      answer: String(item.answer || ""),
      wrong: lines(item.wrongText || ""),
      why: item.why || "",
    }));
  delete data.hintsText;
  delete data.answersText;
  delete data.walkthroughForm;
  delete data.walkthroughEnabled;
  delete data.quizForm;
  return data;
}

function formFromData(data) {
  const walk = data.walkthrough || null;
  return {
    ...blankExercise(data.type),
    ...data,
    simulated_output: data.simulated_output || "",
    expected_output: data.expected_output || "",
    hintsText: (data.hints || []).join("\n"),
    answersText: (data.check?.accepted_answers || []).join("\n"),
    walkthroughEnabled: Boolean(walk),
    walkthroughForm: walk
      ? {
          setup: walk.setup || "",
          stdinText: (walk.stdin || []).join("\n"),
          try_it: walk.try_it || "",
          run: walk.run !== false,
          expect_error: walk.expect_error || "",
          notes: Object.fromEntries(
            Object.entries(walk.notes || {}).map(([key, value]) => [String(key), value]),
          ),
        }
      : blankWalkthrough(),
    quizForm: (data.quiz || []).map((item) => ({
      kind: item.kind === "output" ? "output" : "concept",
      q: item.q || "",
      code: item.code || "",
      answer: item.answer || "",
      wrongText: (item.wrong || []).join("\n"),
      why: item.why || "",
    })),
    check: {
      ...blankExercise().check,
      ...data.check,
      rules: (data.check?.rules || []).map((rule) => ({
        ...rule,
        valuesText: (rule.values || []).join("\n"),
        value: rule.value || "",
        pattern: rule.pattern || "",
        hint: rule.hint || "",
        minimum: rule.minimum ?? "",
        maximum: rule.maximum ?? "",
      })),
    },
  };
}

function ExerciseForm({ lessonId, exercise, onSaved, onDeleted = null }) {
  const [form, setForm] = useState(() =>
    formFromData(exercise?.data || blankExercise(exercise?.type || "recall")),
  );
  const [status, setStatus] = useState(exercise?.status || "draft");
  const [raw, setRaw] = useState(false);
  const [rawText, setRawText] = useState("");
  const [rawFormat, setRawFormat] = useState("json");
  const [attempt, setAttempt] = useState("");
  const [output, setOutput] = useState("");
  const [walkOpen, setWalkOpen] = useState(Boolean(exercise?.data?.walkthrough));
  const [quizOpen, setQuizOpen] = useState((exercise?.data?.quiz || []).length > 0);
  const [preview, setPreview] = useState(null);

  const programLines = useMemo(() => programFromForm(form).split("\n"), [form]);
  const missingNotes = useMemo(() => {
    if (!form.walkthroughEnabled) return [];
    return programLines
      .map((text, index) => ({ line: index + 1, text }))
      .filter(
        (row) =>
          row.text.trim() &&
          !row.text.trim().startsWith("#") &&
          !String(form.walkthroughForm?.notes?.[row.line] || "").trim(),
      );
  }, [form, programLines]);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function updateCheck(patch) {
    setForm((current) => ({ ...current, check: { ...current.check, ...patch } }));
  }

  function updateNormalize(patch) {
    setForm((current) => ({
      ...current,
      check: {
        ...current.check,
        normalize: { ...current.check.normalize, ...patch },
      },
    }));
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      const data = payloadFromForm(form);
      if (exercise?.id) {
        await api(`/api/admin/exercises/${exercise.id}`, {
          method: "PATCH",
          body: { status, data },
        });
      } else {
        await api("/api/admin/exercises", {
          method: "POST",
          body: { lesson_id: lessonId, status, data },
        });
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeExercise() {
    if (!exercise?.id || !onDeleted) {
      return;
    }
    setError("");
    try {
      await api(`/api/admin/exercises/${exercise.id}`, { method: "DELETE" });
      onDeleted();
    } catch (err) {
      setError(err.message);
    }
  }

  async function applyRaw() {
    setError("");
    try {
      const parsed = await api("/api/admin/content/parse-exercise", {
        method: "POST",
        body: { text: rawText, format: rawFormat },
      });
      setForm(formFromData(parsed.data));
      setRaw(false);
    } catch (err) {
      setError(err.message);
    }
  }

  async function testRule(event) {
    event.preventDefault();
    setError("");
    try {
      const outcome = await api("/api/admin/exercises/test-check", {
        method: "POST",
        body: {
          data: payloadFromForm(form),
          attempt,
          output: output || null,
        },
      });
      setResult(
        outcome.passed
          ? "Passed."
          : `Failed${outcome.failed_kind ? ` (${outcome.failed_kind})` : ""}. ${outcome.hint || ""}`,
      );
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={save} className="mt-3 flex flex-col gap-3 rounded-xl bg-bg p-4">
      <div className="flex flex-wrap gap-2">
        <select
          className="rounded-xl border border-muted/30 bg-surface px-3 py-2"
          value={form.type}
          onChange={(event) => update({ type: event.target.value })}
          aria-label="Exercise type"
        >
          {TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <select
          className="rounded-xl border border-muted/30 bg-surface px-3 py-2"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          aria-label="Exercise status"
        >
          <option value="draft">draft</option>
          <option value="published">published</option>
        </select>
        <button
          type="button"
          className="rounded-full border border-muted/30 px-3 py-2 text-sm"
          onClick={() => {
            setRawText(JSON.stringify(payloadFromForm(form), null, 2));
            setRawFormat("json");
            setRaw((value) => !value);
          }}
        >
          {raw ? "Form" : "Raw YAML/JSON"}
        </button>
      </div>
      {raw ? (
        <div className="flex flex-col gap-2">
          <select
            className="w-32 rounded-xl border border-muted/30 bg-surface px-3 py-2"
            value={rawFormat}
            onChange={(event) => setRawFormat(event.target.value)}
            aria-label="Raw format"
          >
            <option value="json">json</option>
            <option value="yaml">yaml</option>
          </select>
          <textarea
            className="min-h-40 rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono text-sm"
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            aria-label="Raw exercise"
          />
          <button
            type="button"
            className="w-fit rounded-full border border-muted/30 px-4 py-2 text-sm"
            onClick={applyRaw}
          >
            Apply raw text
          </button>
        </div>
      ) : (
        <>
          <label className="text-sm">
            Prompt
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
              value={form.prompt}
              onChange={(event) => update({ prompt: event.target.value })}
              required
            />
          </label>
          <label className="text-sm">
            Runtime
            <select
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
              value={form.runtime}
              onChange={(event) => update({ runtime: event.target.value })}
            >
              {RUNTIMES.map((runtime) => (
                <option key={runtime} value={runtime}>
                  {runtime}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Code or ghost text
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
              value={form.code || ""}
              onChange={(event) => update({ code: event.target.value })}
            />
          </label>
          {form.type === "fill" ? (
            <div className="text-sm">
              Blanks
              {form.blanks.map((blank, index) => (
                <div key={blank.index} className="mt-1 flex flex-wrap gap-2">
                  <input
                    className="w-20 rounded-xl border border-muted/30 bg-surface px-3 py-2"
                    type="number"
                    min="1"
                    aria-label={`Blank ${index + 1} index`}
                    value={blank.index}
                    onChange={(event) => {
                      const blanks = form.blanks.slice();
                      blanks[index] = { ...blank, index: Number(event.target.value) };
                      update({ blanks });
                    }}
                  />
                  <input
                    className="min-w-0 w-full flex-1 rounded-xl border border-muted/30 bg-surface px-3 py-2 sm:w-auto"
                    aria-label={`Blank ${index + 1} placeholder`}
                    value={blank.placeholder}
                    onChange={(event) => {
                      const blanks = form.blanks.slice();
                      blanks[index] = { ...blank, placeholder: event.target.value };
                      update({ blanks });
                    }}
                  />
                </div>
              ))}
              <button
                type="button"
                className="mt-2 text-accent"
                onClick={() =>
                  update({
                    blanks: [
                      ...form.blanks,
                      { index: form.blanks.length + 1, placeholder: "____" },
                    ],
                  })
                }
              >
                Add blank
              </button>
            </div>
          ) : null}
          <label className="text-sm">
            Tokens, one per line as match | explanation
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
              value={(form.tokens || [])
                .map((token) => `${token.match} | ${token.explain}`)
                .join("\n")}
              onChange={(event) =>
                update({
                  tokens: lines(event.target.value).map((line) => {
                    const [match, explain] = line.split("|");
                    return { match: (match || "").trim(), explain: (explain || "").trim() };
                  }),
                })
              }
            />
          </label>
          <label className="text-sm">
            Accepted answers, one per line
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
              value={form.answersText || ""}
              onChange={(event) => update({ answersText: event.target.value })}
            />
          </label>
          <label className="text-sm">
            Check mode
            <select
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
              value={form.check.mode}
              onChange={(event) => updateCheck({ mode: event.target.value })}
            >
              <option value="either">either</option>
              <option value="answers">answers</option>
              <option value="rules">rules</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-3 text-sm">
            {[
              ["trim", "Trim"],
              ["collapse_whitespace", "Collapse spaces"],
              ["equivalent_quotes", "Equivalent quotes"],
              ["case_sensitive", "Case sensitive"],
              ["indent_levels", "Indent levels (2≈4 spaces)"],
              ["comma_space", "Comma spacing"],
            ].map(([key, label]) => (
              <label key={key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(form.check.normalize[key])}
                  onChange={(event) => updateNormalize({ [key]: event.target.checked })}
                />
                {label}
              </label>
            ))}
          </div>
          <div className="text-sm">
            Rules
            {form.check.rules.map((rule, index) => (
              <div key={index} className="mt-2 grid gap-2 rounded-xl border border-muted/20 p-3">
                <select
                  aria-label={`Rule ${index + 1} kind`}
                  className="rounded-xl border border-muted/30 bg-surface px-3 py-2"
                  value={rule.kind}
                  onChange={(event) => {
                    const rules = form.check.rules.slice();
                    rules[index] = { ...rule, kind: event.target.value };
                    updateCheck({ rules });
                  }}
                >
                  {KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {kind}
                    </option>
                  ))}
                </select>
                <input
                  className="rounded-xl border border-muted/30 bg-surface px-3 py-2"
                  placeholder="value"
                  aria-label={`Rule ${index + 1} value`}
                  value={rule.value || ""}
                  onChange={(event) => {
                    const rules = form.check.rules.slice();
                    rules[index] = { ...rule, value: event.target.value };
                    updateCheck({ rules });
                  }}
                />
                <textarea
                  className="rounded-xl border border-muted/30 bg-surface px-3 py-2"
                  placeholder="values, one per line"
                  aria-label={`Rule ${index + 1} values`}
                  value={rule.valuesText || ""}
                  onChange={(event) => {
                    const rules = form.check.rules.slice();
                    rules[index] = { ...rule, valuesText: event.target.value };
                    updateCheck({ rules });
                  }}
                />
                <input
                  className="rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                  placeholder="regex"
                  aria-label={`Rule ${index + 1} pattern`}
                  value={rule.pattern || ""}
                  onChange={(event) => {
                    const rules = form.check.rules.slice();
                    rules[index] = { ...rule, pattern: event.target.value };
                    updateCheck({ rules });
                  }}
                />
                <div className="flex gap-2">
                  <input
                    className="w-24 rounded-xl border border-muted/30 bg-surface px-3 py-2"
                    type="number"
                    placeholder="min"
                    aria-label={`Rule ${index + 1} minimum`}
                    value={rule.minimum}
                    onChange={(event) => {
                      const rules = form.check.rules.slice();
                      rules[index] = { ...rule, minimum: event.target.value };
                      updateCheck({ rules });
                    }}
                  />
                  <input
                    className="w-24 rounded-xl border border-muted/30 bg-surface px-3 py-2"
                    type="number"
                    placeholder="max"
                    aria-label={`Rule ${index + 1} maximum`}
                    value={rule.maximum}
                    onChange={(event) => {
                      const rules = form.check.rules.slice();
                      rules[index] = { ...rule, maximum: event.target.value };
                      updateCheck({ rules });
                    }}
                  />
                </div>
                <input
                  className="rounded-xl border border-muted/30 bg-surface px-3 py-2"
                  placeholder="hint"
                  aria-label={`Rule ${index + 1} hint`}
                  value={rule.hint || ""}
                  onChange={(event) => {
                    const rules = form.check.rules.slice();
                    rules[index] = { ...rule, hint: event.target.value };
                    updateCheck({ rules });
                  }}
                />
              </div>
            ))}
            <button
              type="button"
              className="mt-2 text-accent"
              onClick={() =>
                updateCheck({
                  rules: [
                    ...form.check.rules,
                    {
                      kind: "must_contain",
                      value: "",
                      valuesText: "",
                      pattern: "",
                      hint: "",
                      minimum: "",
                      maximum: "",
                    },
                  ],
                })
              }
            >
              Add rule
            </button>
          </div>
          <label className="text-sm">
            Hints, one per line
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
              value={form.hintsText || ""}
              onChange={(event) => update({ hintsText: event.target.value })}
            />
          </label>
          <label className="text-sm">
            Simulated output
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
              value={form.simulated_output}
              onChange={(event) => update({ simulated_output: event.target.value })}
            />
          </label>
          <label className="text-sm">
            Expected output
            <textarea
              className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
              value={form.expected_output}
              onChange={(event) => update({ expected_output: event.target.value })}
            />
          </label>
          <div className="flex gap-2">
            <label className="text-sm">
              XP
              <input
                className="mt-1 w-24 rounded-xl border border-muted/30 bg-surface px-3 py-2"
                type="number"
                min="0"
                value={form.xp}
                onChange={(event) => update({ xp: event.target.value })}
              />
            </label>
            {form.type === "challenge" ? (
              <label className="text-sm">
                Time limit (seconds, blank = untimed)
                <input
                  className="mt-1 w-28 rounded-xl border border-muted/30 bg-surface px-3 py-2"
                  type="number"
                  min="10"
                  max="3600"
                  placeholder="untimed"
                  value={form.time_limit_seconds ?? ""}
                  onChange={(event) => update({ time_limit_seconds: event.target.value })}
                />
              </label>
            ) : null}
          </div>
          <div className="rounded-xl border border-muted/20 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                className="text-sm font-medium text-accent"
                onClick={() => setWalkOpen((value) => !value)}
                aria-expanded={walkOpen}
              >
                {walkOpen ? "Hide walkthrough" : "Walkthrough (step-through)"}
              </button>
              <label className="inline-flex min-h-11 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean(form.walkthroughEnabled)}
                  onChange={(event) => update({ walkthroughEnabled: event.target.checked })}
                />
                Include walkthrough
              </label>
            </div>
            {walkOpen ? (
              <div className="mt-3 flex flex-col gap-3">
                <label className="text-sm">
                  Setup (hidden; runs first)
                  <textarea
                    className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                    value={form.walkthroughForm?.setup || ""}
                    onChange={(event) =>
                      update({
                        walkthroughForm: { ...form.walkthroughForm, setup: event.target.value },
                      })
                    }
                  />
                </label>
                <label className="text-sm">
                  Stdin answers, one per line
                  <textarea
                    className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                    value={form.walkthroughForm?.stdinText || ""}
                    onChange={(event) =>
                      update({
                        walkthroughForm: { ...form.walkthroughForm, stdinText: event.target.value },
                      })
                    }
                  />
                </label>
                <label className="text-sm">
                  try_it (appended so a def can run)
                  <textarea
                    className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                    value={form.walkthroughForm?.try_it || ""}
                    onChange={(event) =>
                      update({
                        walkthroughForm: { ...form.walkthroughForm, try_it: event.target.value },
                      })
                    }
                  />
                </label>
                <label className="inline-flex min-h-11 items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.walkthroughForm?.run === false}
                    onChange={(event) =>
                      update({
                        walkthroughForm: {
                          ...form.walkthroughForm,
                          run: !event.target.checked,
                        },
                      })
                    }
                  />
                  Notes only (do not run)
                </label>
                <label className="text-sm">
                  Expected error type (optional)
                  <input
                    className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                    value={form.walkthroughForm?.expect_error || ""}
                    onChange={(event) =>
                      update({
                        walkthroughForm: {
                          ...form.walkthroughForm,
                          expect_error: event.target.value,
                        },
                      })
                    }
                  />
                </label>
                <div>
                  <p className="text-sm font-medium">Notes per line</p>
                  <ul className="mt-2 flex flex-col gap-2">
                    {programLines.map((text, index) => {
                      const line = index + 1;
                      return (
                        <li key={line} className="grid gap-1 sm:grid-cols-[3rem_1fr_1.2fr]">
                          <span className="font-mono text-xs text-muted">{line}</span>
                          <code className="overflow-auto rounded bg-bg px-2 py-1 font-mono text-xs">
                            {text || " "}
                          </code>
                          <input
                            className="min-h-11 rounded-xl border border-muted/30 bg-surface px-3 text-sm"
                            aria-label={`Note for line ${line}`}
                            value={form.walkthroughForm?.notes?.[line] || ""}
                            onChange={(event) =>
                              update({
                                walkthroughForm: {
                                  ...form.walkthroughForm,
                                  notes: {
                                    ...form.walkthroughForm.notes,
                                    [line]: event.target.value,
                                  },
                                },
                              })
                            }
                          />
                        </li>
                      );
                    })}
                  </ul>
                  {missingNotes.length ? (
                    <p className="mt-2 text-sm text-error" role="status">
                      {missingNotes.length} non-blank line(s) have no note.
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="min-h-11 self-start rounded-xl border border-muted/30 px-4 text-sm"
                  onClick={() => {
                    const payload = payloadFromForm(form);
                    const walk = payload.walkthrough;
                    if (!walk) {
                      setPreview(null);
                      return;
                    }
                    const source = String(payload.code || "").replace(/\n+$/, "") ||
                      (payload.check?.accepted_answers || [])[0] ||
                      "";
                    const program =
                      source.replace(/\n+$/, "") +
                      (walk.try_it?.trim() ? `\n\n${walk.try_it}` : "");
                    setPreview({
                      program,
                      source_lines: source ? source.split("\n").length : 0,
                      setup: walk.setup,
                      stdin: walk.stdin,
                      run: walk.run,
                      expect_error: walk.expect_error,
                      notes: walk.notes,
                    });
                  }}
                >
                  Preview steps
                </button>
                {preview ? (
                  <Suspense fallback={<p className="text-sm text-muted">Loading preview…</p>}>
                    <StepThrough walk={preview} onClose={() => setPreview(null)} />
                  </Suspense>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="rounded-xl border border-muted/20 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                className="text-sm font-medium text-accent"
                onClick={() => setQuizOpen((value) => !value)}
                aria-expanded={quizOpen}
              >
                {quizOpen ? "Hide quiz" : "Quiz"}
              </button>
              <button
                type="button"
                className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm"
                disabled={(form.quizForm || []).length >= 6}
                onClick={() =>
                  update({ quizForm: [...(form.quizForm || []), blankQuizItem()] })
                }
              >
                Add question
              </button>
            </div>
            {quizOpen ? (
              <ul className="mt-3 flex flex-col gap-4">
                {(form.quizForm || []).map((item, index) => {
                  const wrongLines = lines(item.wrongText || "");
                  const matchesAnswer = wrongLines.some(
                    (line) => line === String(item.answer || ""),
                  );
                  return (
                    <li
                      key={`quiz-${index}`}
                      className="rounded-xl border border-muted/20 bg-bg/50 p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium">Question {index + 1}</p>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm"
                            disabled={index === 0}
                            onClick={() => {
                              const next = [...(form.quizForm || [])];
                              [next[index - 1], next[index]] = [next[index], next[index - 1]];
                              update({ quizForm: next });
                            }}
                          >
                            Up
                          </button>
                          <button
                            type="button"
                            className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm"
                            disabled={index >= (form.quizForm || []).length - 1}
                            onClick={() => {
                              const next = [...(form.quizForm || [])];
                              [next[index + 1], next[index]] = [next[index], next[index + 1]];
                              update({ quizForm: next });
                            }}
                          >
                            Down
                          </button>
                          <button
                            type="button"
                            className="min-h-11 rounded-xl border border-error/40 px-3 text-sm text-error"
                            onClick={() =>
                              update({
                                quizForm: (form.quizForm || []).filter((_, i) => i !== index),
                              })
                            }
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                      <label className="mt-2 block text-sm">
                        Kind
                        <select
                          className="mt-1 min-h-11 w-full rounded-xl border border-muted/30 bg-surface px-3"
                          value={item.kind}
                          onChange={(event) => {
                            const next = [...(form.quizForm || [])];
                            next[index] = { ...item, kind: event.target.value };
                            update({ quizForm: next });
                          }}
                        >
                          <option value="concept">concept</option>
                          <option value="output">output</option>
                        </select>
                      </label>
                      <label className="mt-2 block text-sm">
                        Question
                        <input
                          className="mt-1 min-h-11 w-full rounded-xl border border-muted/30 bg-surface px-3"
                          value={item.q}
                          onChange={(event) => {
                            const next = [...(form.quizForm || [])];
                            next[index] = { ...item, q: event.target.value };
                            update({ quizForm: next });
                          }}
                        />
                      </label>
                      <label className="mt-2 block text-sm">
                        Code (optional)
                        <textarea
                          className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                          value={item.code}
                          onChange={(event) => {
                            const next = [...(form.quizForm || [])];
                            next[index] = { ...item, code: event.target.value };
                            update({ quizForm: next });
                          }}
                        />
                      </label>
                      <label className="mt-2 block text-sm">
                        Answer
                        <textarea
                          className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                          value={item.answer}
                          onChange={(event) => {
                            const next = [...(form.quizForm || [])];
                            next[index] = { ...item, answer: event.target.value };
                            update({ quizForm: next });
                          }}
                        />
                      </label>
                      <label className="mt-2 block text-sm">
                        Wrong answers, one per line
                        <textarea
                          className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                          value={item.wrongText}
                          onChange={(event) => {
                            const next = [...(form.quizForm || [])];
                            next[index] = { ...item, wrongText: event.target.value };
                            update({ quizForm: next });
                          }}
                        />
                      </label>
                      {matchesAnswer ? (
                        <p className="mt-2 text-sm text-error" role="status">
                          Wrong answer matches the right answer
                        </p>
                      ) : null}
                      <label className="mt-2 block text-sm">
                        Why
                        <textarea
                          className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
                          value={item.why}
                          onChange={(event) => {
                            const next = [...(form.quizForm || [])];
                            next[index] = { ...item, why: event.target.value };
                            update({ quizForm: next });
                          }}
                        />
                      </label>
                    </li>
                  );
                })}
                {(form.quizForm || []).length === 0 ? (
                  <li className="text-sm text-muted">No quiz questions yet.</li>
                ) : null}
              </ul>
            ) : null}
          </div>
          <div className="rounded-xl border border-muted/20 p-3">
            <p className="text-sm font-medium">Test this rule</p>
            <label className="mt-2 block text-sm">
              Attempt
              <textarea
                className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                value={attempt}
                onChange={(event) => setAttempt(event.target.value)}
              />
            </label>
            <label className="mt-2 block text-sm">
              Output
              <textarea
                className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2 font-mono"
                value={output}
                onChange={(event) => setOutput(event.target.value)}
              />
            </label>
            <button
              type="button"
              className="mt-2 rounded-full border border-muted/30 px-4 py-2 text-sm"
              onClick={testRule}
            >
              Run check
            </button>
            {result ? <p className="mt-2 text-sm">{result}</p> : null}
          </div>
        </>
      )}
      {error ? <p className="text-sm text-error">{error}</p> : null}
      <div className="flex flex-wrap gap-3">
        <button type="submit" className="w-fit rounded-full bg-accent px-4 py-2 text-sm text-white">
          {exercise?.id ? "Save exercise" : "Add exercise"}
        </button>
        {exercise?.id && onDeleted ? (
          <button
            type="button"
            className="w-fit rounded-full border border-error/40 px-4 py-2 text-sm text-error"
            onClick={removeExercise}
          >
            Delete exercise
          </button>
        ) : null}
      </div>
    </form>
  );
}

export default function LessonEditor({ lessonId, onChanged, onClose = null }) {
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);

  async function load() {
    const data = await api(`/api/admin/lessons/${lessonId}`);
    setLesson(data);
  }

  useEffect(() => {
    let cancelled = false;
    api(`/api/admin/lessons/${lessonId}`)
      .then((data) => {
        if (!cancelled) {
          setLesson(data);
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
  }, [lessonId]);

  if (error && !lesson) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!lesson) {
    return <p className="text-sm text-muted">Loading lesson…</p>;
  }

  async function saveLesson(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      const saved = await api(`/api/admin/lessons/${lessonId}`, {
        method: "PATCH",
        body: {
          title: form.get("title"),
          summary: form.get("summary"),
          body_markdown: form.get("body_markdown"),
          status: form.get("status"),
          is_demo: form.get("is_demo") === "on",
          source_type: form.get("source_type"),
          source_attribution: form.get("source_attribution"),
          source_url: form.get("source_url"),
          license_note: form.get("license_note"),
        },
      });
      setLesson(saved);
      setNotice(
        saved.status === "review" && form.get("status") === "published"
          ? "Saved. Published lessons return to review until you publish again."
          : "Lesson saved.",
      );
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  async function publish() {
    setError("");
    try {
      const saved = await api(`/api/admin/lessons/${lessonId}/publish`, { method: "POST" });
      setLesson(saved);
      setNotice("Published.");
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Edit lesson</h2>
        <div className="flex flex-wrap gap-4 text-sm">
          <Link to={`/admin/preview/lessons/${lessonId}`} className="text-accent">
            Preview as learner
          </Link>
          {onClose ? (
            <button type="button" className="text-muted" onClick={onClose}>
              Close
            </button>
          ) : null}
        </div>
      </div>
      {lesson.source_type === "ai_generated" ? (
        <p className="mt-4 rounded-xl border border-accent/40 bg-bg px-3 py-2 text-sm">
          AI-generated — review carefully before publishing.
        </p>
      ) : null}
      <form onSubmit={saveLesson} className="mt-4 grid gap-3">
        <input
          name="title"
          defaultValue={lesson.title}
          required
          className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
          aria-label="Title"
        />
        <input
          name="summary"
          defaultValue={lesson.summary || ""}
          className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
          aria-label="Summary"
        />
        <div className="grid gap-3 lg:grid-cols-2">
          <textarea
            name="body_markdown"
            defaultValue={lesson.body_markdown || ""}
            className="min-h-48 rounded-xl border border-muted/30 bg-bg px-3 py-2 font-mono text-sm"
            aria-label="Markdown"
            onChange={(event) =>
              setLesson((current) => ({ ...current, body_markdown: event.target.value }))
            }
          />
          <div className="rounded-xl border border-muted/20 p-3">
            <MarkdownView text={lesson.body_markdown} />
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            name="status"
            defaultValue={lesson.status === "published" ? "review" : lesson.status}
            className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
            aria-label="Lesson status"
          >
            <option value="draft">draft</option>
            <option value="review">review</option>
          </select>
          <select
            name="source_type"
            defaultValue={lesson.source_type}
            className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
            aria-label="Source type"
          >
            <option value="original">original</option>
            <option value="adapted">adapted</option>
            <option value="ai_generated">ai_generated</option>
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input name="is_demo" type="checkbox" defaultChecked={lesson.is_demo} />
            Demo
          </label>
        </div>
        <input
          name="source_attribution"
          defaultValue={lesson.source_attribution || ""}
          placeholder="Attribution"
          className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
        />
        <input
          name="source_url"
          defaultValue={lesson.source_url || ""}
          placeholder="https://source.example"
          className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
        />
        <input
          name="license_note"
          defaultValue={lesson.license_note || ""}
          placeholder="License note"
          className="rounded-xl border border-muted/30 bg-bg px-3 py-2"
        />
        <p className="text-sm text-muted">
          Current status: {lesson.status}. Saving a published lesson moves it back to review.
        </p>
        {notice ? <p className="text-sm">{notice}</p> : null}
        {error ? <p className="text-sm text-error">{error}</p> : null}
        <div className="flex gap-2">
          <button type="submit" className="rounded-full bg-accent px-4 py-2 text-sm text-white">
            Save lesson
          </button>
          <button
            type="button"
            className="rounded-full border border-muted/30 px-4 py-2 text-sm"
            onClick={publish}
          >
            Publish
          </button>
        </div>
      </form>
      <div className="mt-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-semibold">Exercises</h3>
          {!adding ? (
            <button type="button" className="text-sm text-accent" onClick={() => setAdding(true)}>
              Add exercise
            </button>
          ) : null}
        </div>
        <p className="mt-1 text-sm text-muted">
          Trace, fill, recall, and challenge live here. Open one to edit or delete it.
        </p>
        {lesson.exercises.map((exercise) => (
          <details key={exercise.id} className="mt-3 rounded-xl border border-muted/20 px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium">
              {exercise.order}. {exercise.type} · {exercise.status}
            </summary>
            <div className="mt-3">
              <ExerciseForm
                lessonId={lessonId}
                exercise={exercise}
                onSaved={() => {
                  load().catch((err) => setError(err.message));
                  onChanged();
                }}
                onDeleted={() => {
                  load().catch((err) => setError(err.message));
                  onChanged();
                }}
              />
            </div>
          </details>
        ))}
        {adding ? (
          <div className="mt-3 rounded-xl border border-muted/20 px-4 py-3">
            <p className="text-sm font-medium">New exercise</p>
            <ExerciseForm
              lessonId={lessonId}
              exercise={null}
              onSaved={() => {
                setAdding(false);
                load().catch((err) => setError(err.message));
                onChanged();
              }}
            />
            <button
              type="button"
              className="mt-3 text-sm text-muted"
              onClick={() => setAdding(false)}
            >
              Cancel
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
