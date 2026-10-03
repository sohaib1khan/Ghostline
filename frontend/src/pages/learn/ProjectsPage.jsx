import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { readPrefs } from "../../prefs.js";

const DOT = {
  bash: "bg-accent",
  python: "bg-accent-2",
  go: "bg-success",
  javascript: "bg-muted",
  sql: "bg-[#c4b4d4]",
  csharp: "bg-[#a8b0d4]",
  java: "bg-[#d4a898]",
};

const PROGRESS = {
  new: "Not started",
  started: "In progress",
  done: "Done",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState("");
  const reduce = readPrefs().reduceMotion;

  useEffect(() => {
    let cancelled = false;
    api("/api/learn/projects")
      .then((data) => {
        if (!cancelled) {
          setProjects(data.projects);
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

  return (
    <section className="overflow-hidden rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <div className={reduce ? undefined : "practice-rise"}>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">Advanced path</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Projects</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          After beginner basics and intermediate practice, type a small program end-to-end. Ghost
          text, worked examples, and hints — so harder ideas still stay guided.
        </p>
      </div>
      {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
      {projects === null && !error ? <p className="mt-4 text-sm text-muted">Loading…</p> : null}
      {projects && projects.length === 0 ? (
        <p className="mt-4 text-sm text-muted">
          No projects on your tracks yet. Ask an admin to publish the Projects module, or open a
          track after seed loads.
        </p>
      ) : null}
      {projects && projects.length > 0 ? (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {projects.map((project, index) => (
            <li
              key={project.id}
              className={`project-card rounded-xl border border-muted/20 px-4 py-4 ${
                reduce ? "" : "practice-rise-delay"
              }`}
              style={reduce ? undefined : { animationDelay: `${60 + index * 50}ms` }}
            >
              <p className="flex items-center gap-2 text-xs text-muted">
                <span className={`h-2 w-2 rounded-full ${DOT[project.track_slug] || "bg-accent"}`} />
                {project.track_name}
              </p>
              <Link
                to={`/learn/lessons/${project.id}`}
                className="mt-2 block text-lg font-medium text-accent"
              >
                {project.title}
              </Link>
              {project.summary ? (
                <p className="mt-1 text-sm text-muted">{project.summary}</p>
              ) : null}
              <p className="mt-3 text-xs text-muted">
                Advanced · {PROGRESS[project.progress] || project.progress}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
