import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";

const EMPTY = {
  slug: "",
  order: 0,
  title: "",
  concept: "",
  intro_markdown: "",
  gridText: "###\n#SG\n###",
  startRow: 1,
  startCol: 1,
  facing: "E",
  allowedText: "move",
  goalReach: true,
  goalGems: false,
  max_steps: 500,
  mode: "free",
  starter_code: "",
  solution: "",
  hintsText: "",
  par_lines: 1,
  xp: 20,
  status: "draft",
  python_lesson_slug: "",
};

function parseGrid(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => line.length);
}

function toForm(level) {
  return {
    slug: level.slug || "",
    order: level.order || 0,
    title: level.title || "",
    concept: level.concept || "",
    intro_markdown: level.intro_markdown || "",
    gridText: (level.grid || []).join("\n"),
    startRow: level.start?.row ?? 1,
    startCol: level.start?.col ?? 1,
    facing: level.start?.facing || "E",
    allowedText: (level.allowed || []).join(", "),
    goalReach: level.goal?.reach_goal !== false,
    goalGems: Boolean(level.goal?.collect_all_gems),
    max_steps: level.max_steps || 500,
    mode: level.mode || "free",
    starter_code: level.starter_code || "",
    solution: level.solution || "",
    hintsText: (level.hints || []).join("\n"),
    par_lines: level.par_lines || 1,
    xp: level.xp || 20,
    status: level.status || "draft",
    python_lesson_slug: level.python_lesson_slug || "",
  };
}

function toPayload(form) {
  return {
    slug: form.slug.trim(),
    order: Number(form.order) || 0,
    title: form.title.trim(),
    concept: form.concept.trim(),
    intro_markdown: form.intro_markdown,
    grid: parseGrid(form.gridText),
    start: {
      row: Number(form.startRow),
      col: Number(form.startCol),
      facing: form.facing,
    },
    allowed: form.allowedText
      .split(/[,\s]+/)
      .map((item) => item.trim())
      .filter(Boolean),
    goal: {
      reach_goal: Boolean(form.goalReach),
      collect_all_gems: Boolean(form.goalGems),
    },
    max_steps: Number(form.max_steps) || 500,
    mode: form.mode,
    starter_code: form.starter_code,
    solution: form.solution,
    hints: form.hintsText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    par_lines: Math.max(1, Number(form.par_lines) || 1),
    xp: Number(form.xp) || 20,
    status: form.status,
    python_lesson_slug: form.python_lesson_slug || null,
  };
}

function GridPreview({ gridText }) {
  const rows = parseGrid(gridText);
  return (
    <pre
      className="overflow-auto rounded-xl border border-muted/25 bg-bg p-3 font-mono text-xs leading-tight"
      aria-label="Top-down grid preview"
    >
      {rows.map((row, index) => (
        <div key={`${index}-${row}`}>
          {[...row].map((cell, col) => {
            let mark = cell;
            if (cell === "#") mark = "█";
            if (cell === ".") mark = "·";
            if (cell === "*") mark = "◆";
            if (cell === "G") mark = "◎";
            if (cell === "S") mark = "S";
            return (
              <span key={`${col}-${cell}`} className="inline-block w-3 text-center">
                {mark}
              </span>
            );
          })}
        </div>
      ))}
    </pre>
  );
}

export default function GhostwalkAdminPage() {
  const [levels, setLevels] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);
  const [testResult, setTestResult] = useState(null);

  async function load() {
    const data = await api("/api/admin/ghostwalk/levels");
    setLevels(data.levels || []);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  function field(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function newLevel() {
    setSelectedId(null);
    setForm({ ...EMPTY, order: (levels.at(-1)?.order || 0) + 1 });
    setTestResult(null);
    setNotice("");
  }

  function editLevel(level) {
    setSelectedId(level.id);
    setForm(toForm(level));
    setTestResult(null);
    setNotice("");
  }

  async function save(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setNotice("");
    try {
      const payload = toPayload(form);
      const saved = selectedId
        ? await api(`/api/admin/ghostwalk/levels/${selectedId}`, {
            method: "PUT",
            body: payload,
          })
        : await api("/api/admin/ghostwalk/levels", { method: "POST", body: payload });
      await load();
      setSelectedId(saved.id);
      setForm(toForm(saved));
      setNotice("Saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function testSolution() {
    if (!selectedId) {
      setError("Save the level before testing the solution.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const result = await api(`/api/admin/ghostwalk/levels/${selectedId}/test-solution`, {
        method: "POST",
      });
      setTestResult(result);
      setNotice(result.ok ? "Solution passes replay." : result.error || "Solution failed.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function publish() {
    if (!testResult?.ok) {
      setError("Run Test solution successfully before publishing.");
      return;
    }
    field("status", "published");
    setPending(true);
    try {
      const payload = { ...toPayload(form), status: "published" };
      const saved = await api(`/api/admin/ghostwalk/levels/${selectedId}`, {
        method: "PUT",
        body: payload,
      });
      await load();
      setForm(toForm(saved));
      setNotice("Published.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function exportYaml() {
    const response = await fetch("/api/admin/ghostwalk/export", { credentials: "include" });
    const text = await response.text();
    const blob = new Blob([text], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ghostwalk-levels.yaml";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function move(levelId, direction) {
    const order = [...levels].sort((a, b) => a.order - b.order);
    const index = order.findIndex((item) => item.id === levelId);
    const swap = index + direction;
    if (swap < 0 || swap >= order.length) return;
    const ids = order.map((item) => item.id);
    [ids[index], ids[swap]] = [ids[swap], ids[index]];
    setPending(true);
    try {
      await api("/api/admin/ghostwalk/levels/reorder", {
        method: "POST",
        body: { ordered_ids: ids },
      });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ghostwalk levels</h1>
          <p className="mt-2 text-sm text-muted">
            Build mazes, test solutions in the sandbox, then publish. The server only accepts move
            lists that replay cleanly.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm" onClick={newLevel}>
            New level
          </button>
          <button type="button" className="min-h-11 rounded-xl border border-muted/30 px-3 text-sm" onClick={exportYaml}>
            Export YAML
          </button>
        </div>
      </div>

      {error ? <p className="mt-3 text-sm text-error">{error}</p> : null}
      {notice ? <p className="mt-3 text-sm text-success">{notice}</p> : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(14rem,18rem)_minmax(0,1fr)]">
        <ul className="flex flex-col gap-2">
          {levels.map((level) => (
            <li key={level.id} className="rounded-xl border border-muted/20 p-3">
              <button type="button" className="w-full text-left" onClick={() => editLevel(level)}>
                <p className="font-medium">{level.title}</p>
                <p className="text-xs text-muted">
                  {level.slug} · {level.status} · #{level.order}
                </p>
              </button>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className="min-h-11 text-xs text-accent"
                  disabled={pending}
                  onClick={() => move(level.id, -1)}
                >
                  Up
                </button>
                <button
                  type="button"
                  className="min-h-11 text-xs text-accent"
                  disabled={pending}
                  onClick={() => move(level.id, 1)}
                >
                  Down
                </button>
              </div>
            </li>
          ))}
        </ul>

        <form className="flex flex-col gap-4" onSubmit={save}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="gw-slug" label="Slug" value={form.slug} onChange={(value) => field("slug", value)} />
            <Field
              id="gw-order"
              label="Order"
              type="number"
              value={String(form.order)}
              onChange={(value) => field("order", Number(value))}
            />
            <Field id="gw-title" label="Title" value={form.title} onChange={(value) => field("title", value)} />
            <Field
              id="gw-concept"
              label="Concept"
              value={form.concept}
              onChange={(value) => field("concept", value)}
            />
          </div>
          <label className="block text-sm text-muted" htmlFor="gw-intro">
            Intro markdown
            <textarea
              id="gw-intro"
              className="mt-1 min-h-24 w-full rounded-xl border border-muted/30 bg-bg p-3 text-text"
              value={form.intro_markdown}
              onChange={(event) => field("intro_markdown", event.target.value)}
            />
          </label>
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="block text-sm text-muted" htmlFor="gw-grid">
              Grid
              <textarea
                id="gw-grid"
                className="mt-1 min-h-40 w-full rounded-xl border border-muted/30 bg-bg p-3 font-mono text-sm text-text"
                value={form.gridText}
                onChange={(event) => field("gridText", event.target.value)}
              />
            </label>
            <div>
              <p className="text-sm text-muted">Live preview</p>
              <div className="mt-1">
                <GridPreview gridText={form.gridText} />
              </div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field
              id="gw-row"
              label="Start row"
              type="number"
              value={String(form.startRow)}
              onChange={(value) => field("startRow", Number(value))}
            />
            <Field
              id="gw-col"
              label="Start col"
              type="number"
              value={String(form.startCol)}
              onChange={(value) => field("startCol", Number(value))}
            />
            <label className="block text-sm text-muted" htmlFor="gw-facing">
              Facing
              <select
                id="gw-facing"
                className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
                value={form.facing}
                onChange={(event) => field("facing", event.target.value)}
              >
                {["N", "E", "S", "W"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Field
            id="gw-allowed"
            label="Allowed commands (comma-separated)"
            value={form.allowedText}
            onChange={(value) => field("allowedText", value)}
          />
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="inline-flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                checked={form.goalReach}
                onChange={(event) => field("goalReach", event.target.checked)}
              />
              Reach goal
            </label>
            <label className="inline-flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                checked={form.goalGems}
                onChange={(event) => field("goalGems", event.target.checked)}
              />
              Collect all gems
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <label className="block text-sm text-muted" htmlFor="gw-mode">
              Mode
              <select
                id="gw-mode"
                className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
                value={form.mode}
                onChange={(event) => field("mode", event.target.value)}
              >
                <option value="guided">guided</option>
                <option value="free">free</option>
              </select>
            </label>
            <label className="block text-sm text-muted" htmlFor="gw-status">
              Status
              <select
                id="gw-status"
                className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
                value={form.status}
                onChange={(event) => field("status", event.target.value)}
              >
                <option value="draft">draft</option>
                <option value="published">published</option>
              </select>
            </label>
            <Field
              id="gw-par"
              label="Par lines"
              type="number"
              value={String(form.par_lines)}
              onChange={(value) => field("par_lines", Number(value))}
            />
            <Field
              id="gw-xp"
              label="XP"
              type="number"
              value={String(form.xp)}
              onChange={(value) => field("xp", Number(value))}
            />
          </div>
          <label className="block text-sm text-muted" htmlFor="gw-starter">
            Starter code
            <textarea
              id="gw-starter"
              className="mt-1 min-h-24 w-full rounded-xl border border-muted/30 bg-bg p-3 font-mono text-sm"
              value={form.starter_code}
              onChange={(event) => field("starter_code", event.target.value)}
            />
          </label>
          <label className="block text-sm text-muted" htmlFor="gw-solution">
            Solution
            <textarea
              id="gw-solution"
              className="mt-1 min-h-28 w-full rounded-xl border border-muted/30 bg-bg p-3 font-mono text-sm"
              value={form.solution}
              onChange={(event) => field("solution", event.target.value)}
            />
          </label>
          <label className="block text-sm text-muted" htmlFor="gw-hints">
            Hints (one per line)
            <textarea
              id="gw-hints"
              className="mt-1 min-h-20 w-full rounded-xl border border-muted/30 bg-bg p-3 text-sm"
              value={form.hintsText}
              onChange={(event) => field("hintsText", event.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save"}</SubmitButton>
            <button
              type="button"
              className="min-h-11 rounded-xl border border-muted/30 px-4 text-sm"
              disabled={pending || !selectedId}
              onClick={testSolution}
            >
              Test solution
            </button>
            <button
              type="button"
              className="min-h-11 rounded-xl bg-accent px-4 text-sm font-medium text-on-accent disabled:opacity-50"
              disabled={pending || !selectedId || !testResult?.ok}
              onClick={publish}
            >
              Publish
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
