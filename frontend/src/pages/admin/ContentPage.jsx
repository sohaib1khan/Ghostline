import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client.js";
import LessonEditor from "./LessonEditor.jsx";

// Native drag plus move buttons. @dnd-kit writes inline transforms, and the
// site CSP allows styles only from our own files.
function move(items, fromId, toId) {
  const next = items.slice();
  const from = next.findIndex((item) => item.id === fromId);
  const to = next.findIndex((item) => item.id === toId);
  if (from < 0 || to < 0 || from === to) {
    return items;
  }
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function shift(items, id, direction) {
  const index = items.findIndex((item) => item.id === id);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= items.length) {
    return items;
  }
  return move(items, id, items[target].id);
}

function Action({ children, onClick, danger = false, label }) {
  return (
    <button
      type="button"
      className={`inline-flex min-h-10 items-center px-1 text-sm ${
        danger ? "text-error" : "text-accent"
      }`}
      onClick={onClick}
      aria-label={label}
    >
      {children}
    </button>
  );
}

function MoveButtons({ onShift }) {
  return (
    <>
      <button
        type="button"
        className="inline-flex min-h-10 items-center px-1 text-sm text-muted"
        onClick={() => onShift(-1)}
        aria-label="Move up"
      >
        Up
      </button>
      <button
        type="button"
        className="inline-flex min-h-10 items-center px-1 text-sm text-muted"
        onClick={() => onShift(1)}
        aria-label="Move down"
      >
        Down
      </button>
    </>
  );
}

export default function ContentPage() {
  const [tree, setTree] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploadNotice, setUploadNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [trackId, setTrackId] = useState("");
  const [editingModuleId, setEditingModuleId] = useState("");
  const [documentText, setDocumentText] = useState("");
  const [fileName, setFileName] = useState("");
  const [importMode, setImportMode] = useState("extend");
  const [dryRun, setDryRun] = useState(true);
  const [publishOnImport, setPublishOnImport] = useState(true);
  const [draftModule, setDraftModule] = useState("");
  const [draftTopic, setDraftTopic] = useState("");
  const [draftDifficulty, setDraftDifficulty] = useState("beginner");
  const [draftCount, setDraftCount] = useState(2);
  const [draftTypes, setDraftTypes] = useState(["trace", "recall"]);
  const [drafting, setDrafting] = useState(false);
  const editorRef = useRef(null);
  const uploadResultRef = useRef(null);

  const load = useCallback(async () => {
    setTree(await api("/api/admin/content/tree"));
  }, []);

  useEffect(() => {
    let cancelled = false;
    api("/api/admin/content/tree")
      .then((data) => {
        if (!cancelled) {
          setTree(data);
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
  }, []);

  function openLesson(id) {
    setSelected(id);
    setEditingModuleId("");
    queueMicrotask(() => {
      editorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function reorder(kind, parentId, ids) {
    await api("/api/admin/reorder", {
      method: "POST",
      body: { kind, parent_id: parentId, ids },
    });
    await load();
  }

  async function addModule(event, nextTrackId) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const title = String(new FormData(formEl).get("title") || "").trim();
    if (!title) {
      return;
    }
    await api("/api/admin/modules", {
      method: "POST",
      body: { track_id: nextTrackId, title },
    });
    formEl.reset();
    await load();
  }

  async function saveModule(event, module) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api(`/api/admin/modules/${module.id}`, {
      method: "PATCH",
      body: {
        title: String(form.get("title") || "").trim(),
        description: String(form.get("description") || ""),
        status: form.get("status"),
      },
    });
    setEditingModuleId("");
    await load();
  }

  async function addLesson(event, moduleId) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const title = String(new FormData(formEl).get("title") || "").trim();
    if (!title) {
      return;
    }
    const created = await api("/api/admin/lessons", {
      method: "POST",
      body: {
        module_id: moduleId,
        title,
        summary: "",
        body_markdown: "",
        status: "draft",
        is_demo: false,
        source_type: "original",
        source_attribution: "",
        source_url: "",
        license_note: "",
      },
    });
    formEl.reset();
    openLesson(created.id);
    await load();
  }

  function toggleDraftType(type) {
    setDraftTypes((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type],
    );
  }

  async function generateDraft(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!draftTypes.length) {
      setError("Choose at least one exercise type.");
      return;
    }
    setDrafting(true);
    try {
      const created = await api("/api/admin/ai/generate-lesson", {
        method: "POST",
        body: {
          module_id: draftModule,
          topic: draftTopic,
          difficulty: draftDifficulty,
          exercise_count: Number(draftCount),
          exercise_types: draftTypes,
        },
      });
      setDraftTopic("");
      openLesson(created.id);
      setNotice("Draft saved. Review it before publishing.");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setDrafting(false);
    }
  }

  async function remove(path, clearSelection = true) {
    await api(path, { method: "DELETE" });
    if (clearSelection) {
      setSelected(null);
    }
    await load();
  }

  async function downloadExport(query, fallback) {
    const response = await fetch(`/api/admin/export?${query}`, { credentials: "include" });
    if (!response.ok) {
      setError("Download failed.");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const header = response.headers.get("Content-Disposition") || "";
    const named = /filename="([^"]+)"/.exec(header);
    link.href = url;
    link.download = named?.[1] || fallback;
    link.click();
    URL.revokeObjectURL(url);
  }

  function readImportFile(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setDocumentText(typeof reader.result === "string" ? reader.result : "");
      setFileName(file.name);
    };
    reader.readAsText(file);
  }

  async function importDocument(event) {
    event.preventDefault();
    setUploadError("");
    setUploadNotice("");
    if (!documentText.trim()) {
      setUploadError("Choose a file or paste YAML first.");
      return;
    }
    setUploading(true);
    try {
      const result = await api("/api/admin/import", {
        method: "POST",
        body: {
          document: documentText,
          dry_run: dryRun,
          mode: importMode,
          publish: publishOnImport,
        },
      });
      const label = result.slug === "all" ? "all tracks" : result.slug;
      let message;
      if (result.dry_run) {
        message =
          result.mode === "replace"
            ? `Check passed for ${label}: the file has ${result.lessons} lessons. Nothing was saved. Uncheck “Check without saving” and click Save upload to apply.`
            : `Check passed for ${label}: would add ${result.added_lessons} lessons and update ${result.updated_lessons}. Nothing was saved. Uncheck “Check without saving” and click Save upload to apply.`;
      } else if (result.mode === "replace") {
        message = `Replaced ${label}. Now ${result.lessons} lessons in the file are on the track.`;
      } else {
        message = `Saved to ${label}: ${result.added_lessons} lessons added, ${result.updated_lessons} updated.`;
      }
      if (result.publish) {
        message += " Lessons were marked published for Learn and Games.";
      } else if (result.unpublished_lessons > 0) {
        message += ` ${result.unpublished_lessons} lesson(s) stay draft/review — Publish each lesson (or re-upload with “Publish for practice”) before they appear in Learn or Games.`;
      }
      setUploadNotice(message);
      if (!result.dry_run) {
        await load();
      }
      queueMicrotask(() => {
        uploadResultRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    } catch (err) {
      setUploadError(err.message);
      queueMicrotask(() => {
        uploadResultRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    } finally {
      setUploading(false);
    }
  }

  if (!tree && !error) {
    return <p className="text-sm text-muted">Loading content…</p>;
  }

  const tracks = tree?.tracks || [];
  const active = tracks.find((track) => track.id === trackId) || tracks[0] || null;

  return (
    <div className="flex flex-col gap-8">
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold tracking-tight">Content</h1>
        <p className="mt-2 text-sm text-muted">
          Add modules and lessons here. Edit opens the full lesson, including its exercises.
          Download a lesson to expand it with AI, then upload the file below.
        </p>
        {error ? <p className="mt-3 text-sm text-error">{error}</p> : null}
        {notice ? <p className="mt-3 text-sm text-success">{notice}</p> : null}
        <details className="mt-6 rounded-xl border border-muted/20 px-4 py-3">
          <summary className="min-h-10 cursor-pointer text-sm font-medium">
            Generate draft with AI
          </summary>
          <form className="mt-4 flex max-w-xl flex-col gap-3" onSubmit={generateDraft}>
            <p className="text-sm text-muted">
              Uses the provider saved under AI. A valid reply is stored as a draft. An invalid reply
              saves nothing.
            </p>
            <label className="text-sm">
              Module
              <select
                className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2"
                value={draftModule}
                onChange={(event) => setDraftModule(event.target.value)}
                required
                aria-label="Module for the draft"
              >
                <option value="">Choose a module</option>
                {(tree?.tracks || []).flatMap((track) =>
                  track.modules.map((module) => (
                    <option key={module.id} value={module.id}>
                      {track.name} · {module.title}
                    </option>
                  )),
                )}
              </select>
            </label>
            <label className="text-sm">
              Topic
              <input
                className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2"
                value={draftTopic}
                onChange={(event) => setDraftTopic(event.target.value)}
                required
                aria-label="Draft topic"
              />
            </label>
            <div className="flex flex-wrap gap-3">
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 block rounded-xl border border-muted/30 bg-bg px-3 py-2"
                  value={draftDifficulty}
                  onChange={(event) => setDraftDifficulty(event.target.value)}
                >
                  <option value="beginner">beginner</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </label>
              <label className="text-sm">
                Exercises
                <input
                  type="number"
                  min="1"
                  max="8"
                  className="mt-1 block w-20 rounded-xl border border-muted/30 bg-bg px-3 py-2"
                  value={draftCount}
                  onChange={(event) => setDraftCount(event.target.value)}
                />
              </label>
            </div>
            <fieldset className="flex flex-wrap gap-3 text-sm">
              <legend className="sr-only">Exercise types</legend>
              {["trace", "fill", "recall", "challenge"].map((type) => (
                <label key={type} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={draftTypes.includes(type)}
                    onChange={() => toggleDraftType(type)}
                  />
                  {type}
                </label>
              ))}
            </fieldset>
            <button
              type="submit"
              className="w-fit rounded-full bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
              disabled={drafting}
            >
              {drafting ? "Generating…" : "Generate draft with AI"}
            </button>
          </form>
        </details>
        {tracks.length > 0 ? (
          <div className="mt-6 flex flex-wrap gap-1" role="tablist" aria-label="Tracks">
            {tracks.map((track) => {
              const current = active?.id === track.id;
              return (
                <button
                  key={track.id}
                  type="button"
                  role="tab"
                  aria-selected={current}
                  className={`inline-flex min-h-10 items-center rounded-full px-3.5 text-sm ${
                    current
                      ? "bg-bg text-text shadow-[var(--shadow)]"
                      : "text-muted hover:text-text"
                  }`}
                  onClick={() => {
                    setTrackId(track.id);
                    setSelected(null);
                    setEditingModuleId("");
                  }}
                >
                  {track.name}
                </button>
              );
            })}
          </div>
        ) : null}
        {active ? (
          <div className="mt-6 flex flex-col gap-6">
            <div className="flex flex-col gap-4">
              <h2 className="text-lg font-semibold">
                {active.name}
                {active.is_active ? "" : " (hidden)"}
              </h2>
              <p className="text-sm text-muted">
                Learn and Games only see published lessons. Drafts from an upload stay here until
                you publish them.
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-[#1b1f23]"
                  onClick={async () => {
                    setError("");
                    setNotice("");
                    try {
                      const result = await api(`/api/admin/tracks/${active.id}/publish`, {
                        method: "POST",
                        body: {},
                      });
                      setNotice(
                        `Published ${result.published} lesson(s) on ${result.slug}` +
                          (result.skipped_empty
                            ? ` (${result.skipped_empty} empty skipped).`
                            : "."),
                      );
                      await load();
                    } catch (err) {
                      setError(err.message);
                    }
                  }}
                >
                  Publish all drafts on {active.name}
                </button>
              </div>
              <form
                className="flex flex-wrap items-center gap-3"
                onSubmit={(event) =>
                  addModule(event, active.id).catch((err) => setError(err.message))
                }
              >
                <input
                  name="title"
                  aria-label={`New module in ${active.name}`}
                  placeholder="New module"
                  className="min-w-64 flex-1 rounded-xl border border-muted/30 bg-bg px-3 py-2"
                />
                <button type="submit" className="text-sm text-accent">
                  Add module
                </button>
              </form>
            </div>
            <div className="flex flex-col gap-4">
              {active.modules.map((module) => (
                <div key={module.id} className="rounded-xl border border-muted/20 p-4">
                  <div
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-muted/20 bg-bg px-4 py-3"
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData("text/plain", module.id);
                    }}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      const fromId = event.dataTransfer.getData("text/plain");
                      reorder(
                        "module",
                        active.id,
                        move(active.modules, fromId, module.id).map((item) => item.id),
                      ).catch((err) => setError(err.message));
                    }}
                  >
                    <span className="text-muted" aria-hidden>
                      ::
                    </span>
                    <button
                      type="button"
                      className="min-w-48 flex-1 break-words py-1 text-left font-medium"
                      onClick={() =>
                        setEditingModuleId((current) => (current === module.id ? "" : module.id))
                      }
                    >
                      {module.title} · {module.status}
                    </button>
                    <MoveButtons
                      onShift={(direction) =>
                        reorder(
                          "module",
                          active.id,
                          shift(active.modules, module.id, direction).map((item) => item.id),
                        ).catch((err) => setError(err.message))
                      }
                    />
                    <Action
                      label={`Edit ${module.title}`}
                      onClick={() => setEditingModuleId(module.id)}
                    >
                      Edit
                    </Action>
                    <Action
                      danger
                      label={`Delete ${module.title}`}
                      onClick={() =>
                        remove(`/api/admin/modules/${module.id}`).catch((err) =>
                          setError(err.message),
                        )
                      }
                    >
                      Delete
                    </Action>
                  </div>
                  {editingModuleId === module.id ? (
                    <form
                      className="mt-3 grid gap-3 rounded-xl border border-muted/20 bg-bg p-4"
                      onSubmit={(event) =>
                        saveModule(event, module).catch((err) => setError(err.message))
                      }
                    >
                      <label className="text-sm">
                        Module title
                        <input
                          name="title"
                          defaultValue={module.title}
                          required
                          className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
                        />
                      </label>
                      <label className="text-sm">
                        Description
                        <input
                          name="description"
                          defaultValue={module.description || ""}
                          className="mt-1 w-full rounded-xl border border-muted/30 bg-surface px-3 py-2"
                        />
                      </label>
                      <label className="text-sm">
                        Status
                        <select
                          name="status"
                          defaultValue={module.status}
                          className="mt-1 block rounded-xl border border-muted/30 bg-surface px-3 py-2"
                        >
                          <option value="draft">draft</option>
                          <option value="published">published</option>
                        </select>
                      </label>
                      <div className="flex flex-wrap gap-3">
                        <button type="submit" className="text-sm text-accent">
                          Save module
                        </button>
                        <button
                          type="button"
                          className="text-sm text-muted"
                          onClick={() => setEditingModuleId("")}
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  ) : null}
                  <ul className="mt-4 flex flex-col gap-2">
                    {module.lessons.map((lesson) => {
                      const activeLesson = selected === lesson.id;
                      return (
                        <li
                          key={lesson.id}
                          className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-3 ${
                            activeLesson
                              ? "border-accent bg-bg"
                              : "border-muted/20 bg-bg/60"
                          }`}
                          draggable
                          onDragStart={(event) => {
                            event.dataTransfer.setData("text/plain", lesson.id);
                          }}
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => {
                            event.preventDefault();
                            const fromId = event.dataTransfer.getData("text/plain");
                            reorder(
                              "lesson",
                              module.id,
                              move(module.lessons, fromId, lesson.id).map((item) => item.id),
                            ).catch((err) => setError(err.message));
                          }}
                        >
                          <div className="min-w-48 flex-1">
                            <p className="font-medium">
                              {lesson.title}
                              {lesson.is_demo ? " · demo" : ""}
                            </p>
                            <p className="text-xs text-muted">
                              {lesson.status} · {lesson.exercises.length}{" "}
                              {lesson.exercises.length === 1 ? "exercise" : "exercises"}
                            </p>
                          </div>
                          <MoveButtons
                            onShift={(direction) =>
                              reorder(
                                "lesson",
                                module.id,
                                shift(module.lessons, lesson.id, direction).map((item) => item.id),
                              ).catch((err) => setError(err.message))
                            }
                          />
                          <Action
                            label={`Edit ${lesson.title}`}
                            onClick={() => openLesson(lesson.id)}
                          >
                            Edit
                          </Action>
                          <Action
                            label={`Download ${lesson.title}`}
                            onClick={() =>
                              downloadExport(
                                `lesson=${lesson.id}&format=yaml`,
                                `${lesson.title}.yaml`,
                              )
                            }
                          >
                            Download
                          </Action>
                          <Action
                            danger
                            label={`Delete ${lesson.title}`}
                            onClick={() =>
                              remove(`/api/admin/lessons/${lesson.id}`).catch((err) =>
                                setError(err.message),
                              )
                            }
                          >
                            Delete
                          </Action>
                        </li>
                      );
                    })}
                  </ul>
                  <form
                    className="mt-3 flex flex-wrap gap-2"
                    onSubmit={(event) =>
                      addLesson(event, module.id).catch((err) => setError(err.message))
                    }
                  >
                    <input
                      name="title"
                      aria-label={`New lesson in ${module.title}`}
                      placeholder="New lesson"
                      className="min-w-0 flex-1 rounded-xl border border-muted/30 bg-bg px-3 py-2"
                    />
                    <button type="submit" className="text-sm text-accent">
                      Add lesson
                    </button>
                  </form>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {selected ? (
        <div ref={editorRef}>
          <LessonEditor
            key={selected}
            lessonId={selected}
            onChanged={() => load().catch((err) => setError(err.message))}
            onClose={() => setSelected(null)}
          />
        </div>
      ) : null}

      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h2 className="text-lg font-semibold tracking-tight">Upload lessons</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Download a lesson, expand the YAML with AI, then upload it here. Matching titles are
          updated. New titles are added.
        </p>
        {active ? (
          <p className="mt-3 text-sm">
            <button
              type="button"
              className="text-accent"
              onClick={() =>
                downloadExport(`track=${active.slug}&format=yaml`, `${active.slug}.yaml`)
              }
            >
              Download all of {active.name}
            </button>
            <span className="text-muted"> when you want the whole track in one file.</span>
          </p>
        ) : null}
        <form onSubmit={importDocument} className="mt-6 flex max-w-2xl flex-col gap-4">
          <p className="text-sm text-muted">
            Uploaded lessons feed Learn and Games only when they are{" "}
            <span className="text-text">published</span>. Drafts stay in Content until you publish.
          </p>
          <label className="text-sm">
            File from AI
            <input
              type="file"
              accept=".yaml,.yml,.json,text/yaml,application/json"
              className="mt-1 block w-full text-sm"
              aria-label="Lesson file"
              onChange={readImportFile}
            />
          </label>
          {fileName ? <p className="text-sm text-muted">{fileName}</p> : null}
          <label className="text-sm">
            Or paste YAML
            <textarea
              className="mt-1 min-h-32 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 font-mono text-sm"
              value={documentText}
              onChange={(event) => setDocumentText(event.target.value)}
              aria-label="Import document"
              placeholder={"slug: sql\nmodules:\n  - title: …"}
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(event) => setDryRun(event.target.checked)}
            />
            Check without saving
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={publishOnImport}
              onChange={(event) => setPublishOnImport(event.target.checked)}
            />
            Publish for practice (Learn + Games use these right away)
          </label>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={importMode === "replace"}
              onChange={(event) => setImportMode(event.target.checked ? "replace" : "extend")}
            />
            Replace the track (deletes lessons missing from the file)
          </label>
          {importMode === "replace" && !dryRun ? (
            <p className="text-sm text-error">
              Replace will wipe lessons on that track that are not in the file, including progress
              on them.
            </p>
          ) : null}
          <div ref={uploadResultRef}>
            {uploadError ? (
              <p className="text-sm text-error" role="alert">
                {uploadError}
              </p>
            ) : null}
            {uploadNotice ? (
              <p className="text-sm text-success" role="status">
                {uploadNotice}
              </p>
            ) : null}
          </div>
          <button
            type="submit"
            className="w-fit rounded-full bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
            disabled={uploading}
          >
            {uploading ? "Working…" : dryRun ? "Check file" : "Save upload"}
          </button>
        </form>
      </section>
    </div>
  );
}
