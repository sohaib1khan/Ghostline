import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { readPrefs } from "../../prefs.js";

const PROGRESS = {
  new: "Not started",
  started: "In progress",
  done: "Done",
};

const LEVEL_ORDER = ["beginner", "intermediate", "advanced"];

function sectionProgress(modules) {
  const lessons = modules.flatMap((module) => module.lessons);
  if (!lessons.length) {
    return { done: 0, total: 0, pct: 0 };
  }
  const done = lessons.filter((lesson) => lesson.progress === "done").length;
  return { done, total: lessons.length, pct: Math.round((done / lessons.length) * 100) };
}

function nextLesson(modulesByLevel) {
  for (const level of LEVEL_ORDER) {
    for (const module of modulesByLevel[level] || []) {
      for (const lesson of module.lessons) {
        if (lesson.progress !== "done") {
          return { lesson, module, level };
        }
      }
    }
  }
  return null;
}

export default function TrackPage() {
  const { slug } = useParams();
  const [outline, setOutline] = useState(null);
  const [error, setError] = useState("");
  const reduce = readPrefs().reduceMotion;

  useEffect(() => {
    let cancelled = false;
    api(`/api/learn/tracks/${slug}/outline`)
      .then((data) => {
        if (!cancelled) {
          setOutline(data);
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
  }, [slug]);

  const modulesByLevel = useMemo(() => {
    const groups = { beginner: [], intermediate: [], advanced: [] };
    for (const module of outline?.modules || []) {
      const level = LEVEL_ORDER.includes(module.level) ? module.level : "beginner";
      groups[level].push(module);
    }
    return groups;
  }, [outline]);

  const continueAt = outline ? nextLesson(modulesByLevel) : null;
  const path = outline?.path || [
    { id: "beginner", label: "Beginner", blurb: "Basics first." },
    { id: "intermediate", label: "Intermediate", blurb: "More programming." },
    { id: "advanced", label: "Advanced", blurb: "Put it together." },
  ];

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      {error ? <p className="text-sm text-error">{error}</p> : null}
      {!outline && !error ? <p className="text-sm text-muted">Loading…</p> : null}
      {outline ? (
        <>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">Learning path</p>
          <h1
            className={`mt-2 text-2xl font-semibold tracking-tight ${reduce ? "" : "practice-rise"}`}
          >
            {outline.name}
          </h1>
          <p className="mt-2 text-sm text-muted">{outline.description}</p>
          <p className="mt-3 max-w-2xl text-sm text-muted">
            Start with beginner basics, then intermediate practice that introduces more programming,
            then advanced projects. Each step builds on the last — type it, use hints, keep going.
          </p>

          <ol className="mt-6 grid gap-3 sm:grid-cols-3">
            {path.map((step, index) => {
              const stats = sectionProgress(modulesByLevel[step.id] || []);
              return (
                <li
                  key={step.id}
                  className={`level-card level-${step.id} rounded-xl border border-muted/20 px-4 py-3 ${
                    reduce ? "" : "practice-rise-delay"
                  }`}
                  style={reduce ? undefined : { animationDelay: `${index * 80}ms` }}
                >
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">
                    Step {index + 1}
                  </p>
                  <p className="mt-1 font-medium">{step.label}</p>
                  <p className="mt-1 text-xs text-muted">{step.blurb}</p>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/20">
                    <div
                      className="lesson-bar h-full rounded-full bg-accent"
                      style={{ width: `${stats.pct}%` }}
                    />
                  </div>
                  <p className="mt-2 font-mono text-xs text-muted">
                    {stats.done}/{stats.total} lessons
                  </p>
                </li>
              );
            })}
          </ol>

          {continueAt ? (
            <p className="mt-6 text-sm">
              <Link
                to={`/learn/lessons/${continueAt.lesson.id}`}
                className="rounded-xl bg-accent px-4 py-2 font-medium text-on-accent"
              >
                {continueAt.lesson.progress === "new" ? "Start here" : "Continue"}:{" "}
                {continueAt.lesson.title}
              </Link>
              <span className="ml-3 text-muted">
                {continueAt.module.level_label} · {continueAt.module.title}
              </span>
            </p>
          ) : (
            <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
              <p className="text-success">Path complete — revisit any lesson to stay sharp.</p>
              <Link to={`/certificates/${slug}`} className="btn-primary">
                View certificate
              </Link>
            </div>
          )}
          {continueAt ? (
            <p className="mt-3 text-sm text-muted">
              <Link to={`/certificates/${slug}`} className="text-accent">
                Preview certificate
              </Link>{" "}
              (watermarked until the path is finished)
            </p>
          ) : null}

          <div className="mt-10 flex flex-col gap-10">
            {path.map((step) => {
              const modules = modulesByLevel[step.id] || [];
              if (!modules.length) {
                return null;
              }
              const stats = sectionProgress(modules);
              return (
                <section key={step.id} className={`level-section level-${step.id}`}>
                  <div className="flex flex-wrap items-end justify-between gap-3 border-b border-muted/15 pb-3">
                    <div>
                      <h2 className="text-lg font-semibold tracking-tight">{step.label}</h2>
                      <p className="mt-1 text-sm text-muted">{step.blurb}</p>
                    </div>
                    <p className="font-mono text-xs text-muted">
                      {stats.done}/{stats.total} done
                    </p>
                  </div>
                  <div className="mt-4 flex flex-col gap-5">
                    {modules.map((module) => (
                      <div
                        key={module.id}
                        className={
                          module.title === "Projects" ? "project-module" : undefined
                        }
                      >
                        <h3 className="font-medium">
                          {module.title}
                          {module.title === "Daily scripts" ? (
                            <span className="ml-2 font-mono text-xs font-normal uppercase tracking-wider text-accent">
                              guided practice
                            </span>
                          ) : null}
                          {module.title === "Projects" ? (
                            <span className="ml-2 font-mono text-xs font-normal uppercase tracking-wider text-accent">
                              apply it
                            </span>
                          ) : null}
                        </h3>
                        {module.description ? (
                          <p className="mt-1 text-sm text-muted">{module.description}</p>
                        ) : null}
                        {module.lessons.length === 0 ? (
                          <p className="mt-2 text-sm text-muted">No published lessons yet.</p>
                        ) : (
                          <ul className="mt-3 flex flex-col gap-2">
                            {module.lessons.map((lesson) => (
                              <li
                                key={lesson.id}
                                className="lesson-row rounded-xl border border-transparent px-2 py-2 transition hover:border-muted/25 hover:bg-bg/60"
                              >
                                <Link
                                  to={`/learn/lessons/${lesson.id}`}
                                  className="text-accent"
                                >
                                  {lesson.title}
                                </Link>
                                {lesson.is_demo ? (
                                  <span className="ml-2 text-sm text-muted">Demo</span>
                                ) : null}
                                {lesson.progress ? (
                                  <span className="ml-2 text-sm text-muted">
                                    {PROGRESS[lesson.progress] || lesson.progress}
                                  </span>
                                ) : null}
                                {lesson.summary ? (
                                  <p className="text-sm text-muted">{lesson.summary}</p>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        </>
      ) : null}
    </section>
  );
}
