import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import TrackLogo from "../../components/content/TrackLogo.jsx";

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
    <div className="landing">
      <section className="landing-hero landing-hero-compact" aria-labelledby="demo-title">
        <p className="landing-kicker">Free demo</p>
        <h1 id="demo-title" className="landing-title">
          Feel the keystrokes before you sign up.
        </h1>
        <p className="landing-lead">
          Short published teasers — no account, no save. Sign in later from the nav if you want a
          streak, full tracks, games, and the playground.
        </p>
        <div className="landing-cta">
          <a
            href="https://github.com/sohaib1khan/Ghostline"
            className="btn-secondary"
            target="_blank"
            rel="noreferrer"
          >
            View on GitHub
          </a>
        </div>
      </section>

      <section className="landing-section" aria-labelledby="demo-pick">
        <h2 id="demo-pick" className="landing-section-title">
          Pick a language
        </h2>
        <p className="landing-section-lead">
          Choose a track, then open a lesson. Trace over the guide, use hints if you stall, and
          check your answer when you are ready.
        </p>
        {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
        {catalog === null && !error ? <p className="mt-4 text-sm text-muted">Loading…</p> : null}
        {catalog && catalog.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No demo lessons are published yet.</p>
        ) : null}
        {catalog && catalog.length > 0 ? (
          <>
            <div className="landing-demo-tabs" role="tablist" aria-label="Tracks">
              {catalog.map((track) => (
                <button
                  key={track.slug}
                  type="button"
                  role="tab"
                  aria-selected={track.slug === slug}
                  onClick={() => setSlug(track.slug)}
                  className={`landing-demo-tab ${track.slug === slug ? "is-active" : ""}`}
                >
                  <TrackLogo slug={track.slug} size="sm" title={track.name} />
                  {track.name}
                </button>
              ))}
            </div>
            {selected ? (
              <div className="mt-6">
                <p className="flex flex-wrap items-center gap-2 font-medium text-text">
                  <TrackLogo slug={selected.slug} size="sm" title={selected.name} />
                  {selected.name}
                </p>
                <p className="mt-1 text-sm text-muted">{selected.description}</p>
                <ul className="landing-demo-lessons">
                  {selected.lessons.map((lesson) => (
                    <li key={lesson.id}>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-text">{lesson.title}</p>
                        {lesson.summary ? (
                          <p className="mt-1 text-sm text-muted">{lesson.summary}</p>
                        ) : null}
                      </div>
                      <Link to={`/demo/lessons/${lesson.id}`} className="btn-primary shrink-0">
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

      <footer className="landing-foot">
        <p>
          Made by <span className="text-text">Sohaib Khan</span>
          <span className="landing-foot-sep" aria-hidden="true">
            ·
          </span>
          <a
            href="https://github.com/sohaib1khan/Ghostline"
            target="_blank"
            rel="noreferrer"
            className="landing-foot-link"
          >
            Ghostline on GitHub
          </a>
        </p>
        <p className="landing-foot-note">Self-hosted. Open source. Typing-first.</p>
      </footer>
    </div>
  );
}
