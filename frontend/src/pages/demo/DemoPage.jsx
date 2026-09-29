import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";

const DOT = {
  bash: "bg-accent",
  python: "bg-accent-2",
  go: "bg-success",
  javascript: "bg-muted",
  sql: "bg-[#c4b4d4]",
};

export default function DemoPage() {
  const [catalog, setCatalog] = useState(null);
  const [slug, setSlug] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/demo/tracks")
      .then((data) => {
        if (!cancelled) {
          setCatalog(data.tracks);
          setSlug(data.tracks[0]?.slug || "");
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

  const selected = catalog?.find((track) => track.slug === slug) || null;

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Try a lesson</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Feel the ghost text, then type over it. Demos are short teasers — after you
        sign in, Daily scripts add longer guided challenges with progressive hints.
      </p>
      {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
      {catalog === null && !error ? <p className="mt-4 text-sm text-muted">Loading…</p> : null}
      {catalog && catalog.length === 0 ? (
        <p className="mt-4 text-sm text-muted">No demo lessons are published yet.</p>
      ) : null}
      {catalog && catalog.length > 0 ? (
        <>
          <div className="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Tracks">
            {catalog.map((track) => (
              <button
                key={track.slug}
                type="button"
                role="tab"
                aria-selected={track.slug === slug}
                onClick={() => setSlug(track.slug)}
                className={`rounded-full border px-4 py-2 text-sm ${
                  track.slug === slug
                    ? "border-accent bg-accent text-[#1b1f23]"
                    : "border-muted/30 text-muted"
                }`}
              >
                {track.name}
              </button>
            ))}
          </div>
          {selected ? (
            <div className="mt-6">
              <p className="flex items-center gap-2 font-medium">
                <span className={`h-2.5 w-2.5 rounded-full ${DOT[selected.slug] || "bg-accent"}`} />
                {selected.name}
              </p>
              <p className="mt-1 text-sm text-muted">{selected.description}</p>
              <ul className="mt-4 flex flex-col gap-3">
                {selected.lessons.map((lesson) => (
                  <li key={lesson.id} className="rounded-xl border border-muted/20 px-4 py-3">
                    <p className="font-medium">{lesson.title}</p>
                    {lesson.summary ? (
                      <p className="mt-1 text-sm text-muted">{lesson.summary}</p>
                    ) : null}
                    <Link
                      to={`/demo/lessons/${lesson.id}`}
                      className="mt-2 inline-block text-sm text-accent"
                    >
                      Start
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
