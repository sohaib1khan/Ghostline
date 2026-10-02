import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import {
  CertificateDocument,
  DEMO_CERTIFICATE,
} from "../../components/certificates/CertificateDocument.jsx";
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
  const demoCert = {
    ...DEMO_CERTIFICATE,
    track_slug: selected?.slug || DEMO_CERTIFICATE.track_slug,
    track_name: selected?.name || DEMO_CERTIFICATE.track_name,
    body: `has successfully completed the ${selected?.name || DEMO_CERTIFICATE.track_name} learning path.`,
  };

  return (
    <div className="landing">
      <section className="landing-hero landing-hero-compact" aria-labelledby="demo-title">
        <p className="landing-kicker">Free demo</p>
        <h1 id="demo-title" className="landing-title">
          Feel the keystrokes before you sign up.
        </h1>
        <p className="landing-lead">
          Short published teasers — no account, no save. Sign in later for streaks, full tracks,
          games, playground, and a certificate with your name when a path is complete.
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
          <Link to="/signup" className="btn-ghost">
            Sign up for certificates
          </Link>
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

      <section className="landing-section" aria-labelledby="demo-certificate">
        <h2 id="demo-certificate" className="landing-section-title">
          What a certificate looks like
        </h2>
        <p className="landing-section-lead">
          This sample uses a demo name. After you create an account and finish{" "}
          {selected?.name || "a track"}, your profile name and a real certificate ID appear here —
          print or save as PDF.
        </p>
        <div className="landing-certificate-demo mt-5">
          <CertificateDocument
            cert={demoCert}
            forceWatermark
            watermarkLabel="Demo"
            watermarkHint="Not an official award"
          />
        </div>
        <div className="landing-cta mt-5">
          <Link to="/signup" className="btn-primary">
            Sign up to earn yours
          </Link>
          <Link to="/login" className="btn-secondary">
            Log in
          </Link>
        </div>
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
