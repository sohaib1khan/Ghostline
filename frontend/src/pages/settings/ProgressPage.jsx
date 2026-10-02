import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client.js";
import { SubmitButton } from "../../components/layout/Field.jsx";

const LEVELS = [
  { id: "beginner", label: "Beginner" },
  { id: "intermediate", label: "Intermediate" },
  { id: "advanced", label: "Advanced" },
];

function sectionProgress(modules) {
  const lessons = modules.flatMap((module) => module.lessons || []);
  const done = lessons.filter((lesson) => lesson.progress === "done").length;
  return { done, total: lessons.length };
}

export default function ProgressPage() {
  const [tracks, setTracks] = useState([]);
  const [trackSlug, setTrackSlug] = useState("");
  const [outline, setOutline] = useState(null);
  const [scope, setScope] = useState("track");
  const [level, setLevel] = useState("beginner");
  const [moduleId, setModuleId] = useState("");
  const [lessonId, setLessonId] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/learn/dashboard")
      .then((data) => {
        if (cancelled) {
          return;
        }
        const list = data.tracks || [];
        setTracks(list);
        setTrackSlug((current) => current || list[0]?.slug || "");
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

  useEffect(() => {
    if (!trackSlug || scope === "all") {
      setOutline(null);
      return undefined;
    }
    let cancelled = false;
    setOutline(null);
    api(`/api/learn/tracks/${trackSlug}/outline`)
      .then((data) => {
        if (!cancelled) {
          setOutline(data);
          setModuleId("");
          setLessonId("");
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
  }, [trackSlug, scope]);

  const modulesByLevel = useMemo(() => {
    const groups = { beginner: [], intermediate: [], advanced: [] };
    for (const module of outline?.modules || []) {
      const band = LEVELS.some((item) => item.id === module.level) ? module.level : "beginner";
      groups[band].push(module);
    }
    return groups;
  }, [outline]);

  const modules = outline?.modules || [];
  const selectedModule = modules.find((item) => item.id === moduleId);
  const lessons = selectedModule?.lessons || [];

  const summary = useMemo(() => {
    if (scope === "all") {
      return "all languages";
    }
    const track = tracks.find((item) => item.slug === trackSlug);
    const name = track?.name || trackSlug;
    if (scope === "track") {
      return name;
    }
    if (scope === "level") {
      const label = LEVELS.find((item) => item.id === level)?.label || level;
      const stats = sectionProgress(modulesByLevel[level] || []);
      return `${name} · ${label} (${stats.done}/${stats.total} done)`;
    }
    if (scope === "module") {
      return selectedModule ? `${name} · ${selectedModule.title}` : name;
    }
    const lesson = lessons.find((item) => item.id === lessonId);
    return lesson ? `${name} · ${lesson.title}` : name;
  }, [
    scope,
    tracks,
    trackSlug,
    level,
    modulesByLevel,
    selectedModule,
    lessons,
    lessonId,
  ]);

  const canSubmit =
    confirm &&
    !pending &&
    (scope === "all" ||
      (scope === "track" && trackSlug) ||
      (scope === "level" && trackSlug && level) ||
      (scope === "module" && moduleId) ||
      (scope === "lesson" && lessonId));

  async function onReset(event) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setError("");
    setNotice("");
    setPending(true);
    try {
      const body = { scope };
      if (scope === "track" || scope === "level") {
        body.track_slug = trackSlug;
      }
      if (scope === "level") {
        body.level = level;
      }
      if (scope === "module") {
        body.module_id = moduleId;
      }
      if (scope === "lesson") {
        body.lesson_id = lessonId;
      }
      const result = await api("/api/me/progress/reset", { method: "POST", body });
      setConfirm(false);
      setNotice(
        result.cleared
          ? `Cleared ${result.cleared} exercise${result.cleared === 1 ? "" : "s"} for ${result.label}. XP is now ${result.xp_total}.`
          : `Nothing to clear for ${result.label}.`,
      );
      if (trackSlug && scope !== "all") {
        const refreshed = await api(`/api/learn/tracks/${trackSlug}/outline`);
        setOutline(refreshed);
      }
      const dash = await api("/api/learn/dashboard");
      setTracks(dash.tracks || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Progress</h1>
      <p className="mt-2 max-w-xl text-sm text-muted">
        Reset lesson completion for a language, a step (Beginner / Intermediate / Advanced), a
        module, or one lesson — the same slices you see on the learning path.
      </p>

      <form className="mt-6 flex max-w-lg flex-col gap-5" onSubmit={onReset}>
        <fieldset className="flex flex-col gap-2 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">What to reset</legend>
          {[
            { id: "all", label: "Everything (all languages)" },
            { id: "track", label: "One language (entire track)" },
            { id: "level", label: "One step (Beginner / Intermediate / Advanced)" },
            { id: "module", label: "One module (e.g. Looking around)" },
            { id: "lesson", label: "One lesson" },
          ].map((option) => (
            <label key={option.id} className="flex items-center gap-2 text-sm" htmlFor={`scope-${option.id}`}>
              <input
                id={`scope-${option.id}`}
                type="radio"
                name="scope"
                checked={scope === option.id}
                onChange={() => {
                  setScope(option.id);
                  setConfirm(false);
                  setNotice("");
                }}
              />
              {option.label}
            </label>
          ))}
        </fieldset>

        {scope !== "all" ? (
          <label className="block text-sm text-muted" htmlFor="reset-track">
            Language
            <select
              id="reset-track"
              value={trackSlug}
              onChange={(event) => {
                setTrackSlug(event.target.value);
                setConfirm(false);
                setNotice("");
              }}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              {tracks.map((track) => (
                <option key={track.slug} value={track.slug}>
                  {track.name}
                  {typeof track.completed === "number"
                    ? ` (${track.completed}/${track.total})`
                    : ""}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {scope === "level" ? (
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium text-text">Step</legend>
            {LEVELS.map((item) => {
              const stats = sectionProgress(modulesByLevel[item.id] || []);
              return (
                <label key={item.id} className="flex items-center gap-2 text-sm" htmlFor={`level-${item.id}`}>
                  <input
                    id={`level-${item.id}`}
                    type="radio"
                    name="level"
                    checked={level === item.id}
                    onChange={() => {
                      setLevel(item.id);
                      setConfirm(false);
                    }}
                  />
                  {item.label}
                  {outline ? (
                    <span className="text-muted">
                      · {stats.done}/{stats.total} lessons
                    </span>
                  ) : null}
                </label>
              );
            })}
          </fieldset>
        ) : null}

        {scope === "module" || scope === "lesson" ? (
          <label className="block text-sm text-muted" htmlFor="reset-module">
            Module
            <select
              id="reset-module"
              value={moduleId}
              onChange={(event) => {
                setModuleId(event.target.value);
                setLessonId("");
                setConfirm(false);
              }}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              <option value="">Select a module</option>
              {modules.map((module) => (
                <option key={module.id} value={module.id}>
                  {module.level_label ? `${module.level_label} · ` : ""}
                  {module.title}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {scope === "lesson" ? (
          <label className="block text-sm text-muted" htmlFor="reset-lesson">
            Lesson
            <select
              id="reset-lesson"
              value={lessonId}
              disabled={!moduleId}
              onChange={(event) => {
                setLessonId(event.target.value);
                setConfirm(false);
              }}
              className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text disabled:opacity-50"
            >
              <option value="">Select a lesson</option>
              {lessons.map((lesson) => (
                <option key={lesson.id} value={lesson.id}>
                  {lesson.title}
                  {lesson.progress === "done" ? " · Done" : ""}
                  {lesson.progress === "started" ? " · In progress" : ""}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <p className="rounded-xl border border-muted/20 bg-bg px-3 py-2 text-sm text-muted">
          Will reset: <span className="text-text">{summary}</span>
        </p>

        <label className="flex items-start gap-2 text-sm" htmlFor="reset-confirm">
          <input
            id="reset-confirm"
            type="checkbox"
            className="mt-1"
            checked={confirm}
            onChange={(event) => setConfirm(event.target.checked)}
          />
          <span>
            I understand this clears Done / In progress for the selection. It cannot be undone.
            XP is recalculated from what remains.
          </span>
        </label>

        <SubmitButton disabled={!canSubmit}>{pending ? "Resetting…" : "Reset progress"}</SubmitButton>
      </form>

      {notice ? <p className="mt-4 text-sm text-success">{notice}</p> : null}
      {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
    </section>
  );
}
