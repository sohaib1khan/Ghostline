import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../api/client.js";
import {
  CertificateDocument,
  DEMO_CERTIFICATE,
} from "../components/certificates/CertificateDocument.jsx";
import TrackLogo from "../components/content/TrackLogo.jsx";
import StreakFlame from "../components/feedback/StreakFlame.jsx";
import { readPrefs } from "../prefs.js";
import { isStaff, isSuperAdmin } from "../roles.js";

const TRACK_META = {
  bash: {
    focus: ["Commands", "Pipes", "Scripts"],
    sample: "ls -la | grep conf",
    tip: "Start with listing, paths, then redirection.",
    level: "Shell foundations",
  },
  python: {
    focus: ["Syntax", "Lists", "Functions"],
    sample: "nums.append(3)",
    tip: "Trace print and lists before branching.",
    level: "First programs",
  },
  go: {
    focus: ["Packages", "defer", "Loops"],
    sample: "defer f.Close()",
    tip: "Tiny programs first — fmt, then control flow.",
    level: "Typed flow",
  },
  javascript: {
    focus: ["const", "Functions", "DOM basics"],
    sample: "const name = 'ghost'",
    tip: "Declarations and console output before the browser.",
    level: "Page scripting",
  },
  sql: {
    focus: ["SELECT", "WHERE", "JOIN"],
    sample: "SELECT title FROM books WHERE year > 2000",
    tip: "Filter rows before you aggregate or join.",
    level: "Query literacy",
  },
  csharp: {
    focus: ["Console", "var", "Loops"],
    sample: 'Console.WriteLine("hello");',
    tip: "Main and WriteLine first, then flow.",
    level: "Typed console",
  },
  java: {
    focus: ["println", "types", "Loops"],
    sample: 'System.out.println("hello");',
    tip: "main and System.out before branching.",
    level: "Typed console",
  },
};

function streakNote(days) {
  if (!days) {
    return "A short session today starts the streak that keeps syntax in your fingers.";
  }
  if (days === 1) {
    return "Day one is on. Come back tomorrow and the path stays warm.";
  }
  if (days < 7) {
    return `${days} days in a row. Muscle memory grows with quiet, steady reps.`;
  }
  return `${days}-day streak. That is how commands stop feeling foreign.`;
}

function pct(completed, total) {
  if (!total) {
    return 0;
  }
  return Math.min(100, Math.round((completed / total) * 100));
}

function statusLabel(completed, total) {
  if (!total) {
    return "Empty";
  }
  if (completed <= 0) {
    return "Not started";
  }
  if (completed >= total) {
    return "Complete";
  }
  if (completed / total < 0.25) {
    return "Getting started";
  }
  if (completed / total < 0.75) {
    return "In progress";
  }
  return "Almost there";
}

function latestWpm(trend) {
  if (!trend?.length) {
    return null;
  }
  return trend[trend.length - 1]?.wpm ?? null;
}

function StatChip({ label, value, hint }) {
  return (
    <div className="home-stat">
      <p className="home-stat-label">{label}</p>
      <p className="home-stat-value">{value}</p>
      {hint ? <p className="home-stat-hint">{hint}</p> : null}
    </div>
  );
}

export default function HomePage() {
  const { user } = useOutletContext();
  const [tracks, setTracks] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const reduce = readPrefs().reduceMotion;

  useEffect(() => {
    if (!user) {
      return undefined;
    }
    let cancelled = false;
    Promise.all([api("/api/learn/dashboard"), api("/api/me/stats")])
      .then(([board, meStats]) => {
        if (!cancelled) {
          setTracks(board);
          setStats(meStats);
          setError("");
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
  }, [user]);

  if (!user) {
    return (
      <div className="landing">
        <section className="landing-hero" aria-labelledby="landing-title">
          <p className="landing-kicker">Ghostline</p>
          <h1 id="landing-title" className="landing-title">
            Type the line until your hands know it.
          </h1>
          <p className="landing-lead">
            A calm learning path for Bash, Python, Go, JavaScript, SQL, C#, and Java — beginner basics,
            intermediate practice, then advanced projects you type end to end.
          </p>
          <p className="landing-sample" aria-hidden="true">
            <span className="landing-sample-prompt">$</span>
            <span> echo </span>
            <span className="ghost-text ghost-breathe">&quot;hello, ghostline&quot;</span>
            <span className="ghost-type-marker ghost-type-marker-inline" />
          </p>
          <div className="landing-cta">
            <Link to="/demo" className="btn-primary">
              Try a free lesson
            </Link>
            <a
              href="https://github.com/sohaib1khan/Ghostline"
              className="btn-secondary"
              target="_blank"
              rel="noreferrer"
            >
              View on GitHub
            </a>
          </div>
          <p className="landing-cta-note">
            No account needed for the demo. Sign in from the nav when you want streaks and saved
            progress.
          </p>
        </section>

        <section className="landing-section" aria-labelledby="landing-path">
          <h2 id="landing-path" className="landing-section-title">
            How the path works
          </h2>
          <p className="landing-section-lead">
            Lessons are short on purpose. You type real commands and code; the server checks what
            you typed — it does not run your code on the server.
          </p>
          <ol className="landing-steps">
            <li>
              <span className="landing-step-num">1</span>
              <div>
                <p className="landing-step-title">Beginner</p>
                <p className="landing-step-body">
                  One-liners and core syntax until the shape of each command feels familiar.
                </p>
              </div>
            </li>
            <li>
              <span className="landing-step-num">2</span>
              <div>
                <p className="landing-step-title">Intermediate</p>
                <p className="landing-step-body">
                  Longer guided scripts with progressive hints — daily practice that builds on the
                  basics.
                </p>
              </div>
            </li>
            <li>
              <span className="landing-step-num">3</span>
              <div>
                <p className="landing-step-title">Advanced</p>
                <p className="landing-step-body">
                  Mini-projects you type end to end so the pieces finally sit together.
                </p>
              </div>
            </li>
          </ol>
        </section>

        <section className="landing-section" aria-labelledby="landing-practice">
          <h2 id="landing-practice" className="landing-section-title">
            Ways you practice
          </h2>
          <ul className="landing-modes">
            <li>
              <p className="landing-mode-title">Trace</p>
              <p className="landing-mode-body">
                Type over a guided line until the keystrokes stick in your fingers.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Fill &amp; recall</p>
              <p className="landing-mode-body">
                Complete blanks, then write the line from memory when you are ready.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Games</p>
              <p className="landing-mode-body">
                Short drills reuse the same published lines — hangman, output prediction, and more.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Playground</p>
              <p className="landing-mode-body">
                After you sign in, try ideas in a throwaway box that resets on its own.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Certificates</p>
              <p className="landing-mode-body">
                Finish a path and earn a printable certificate with your profile name on it.
              </p>
            </li>
          </ul>
        </section>

        <section className="landing-section" aria-labelledby="landing-certificate">
          <h2 id="landing-certificate" className="landing-section-title">
            Finish a path. Earn the certificate.
          </h2>
          <p className="landing-section-lead">
            After you sign in, your real name appears on the award. Guests can peek at a sample
            below — the watermark reminds you it is a demo until the path is complete.
          </p>
          <div className="landing-certificate-demo mt-5">
            <CertificateDocument
              cert={DEMO_CERTIFICATE}
              forceWatermark
              watermarkLabel="Demo"
              watermarkHint="Sign in · finish a path · unlock yours"
            />
          </div>
          <div className="landing-cta mt-5">
            <Link to="/demo" className="btn-primary">
              Try a free lesson
            </Link>
            <Link to="/signup" className="btn-secondary">
              Sign up to earn yours
            </Link>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-langs">
          <h2 id="landing-langs" className="landing-section-title">
            Languages on the path
          </h2>
          <p className="landing-section-lead">
            Pick a track in the free demo, or unlock the full ladder when you create an account.
          </p>
          <ul className="landing-langs">
            {[
              { slug: "bash", name: "Bash", blurb: "Shell, paths, pipes, and scripts." },
              { slug: "python", name: "Python", blurb: "Syntax, lists, and first programs." },
              { slug: "go", name: "Go", blurb: "Packages, loops, and typed flow." },
              { slug: "javascript", name: "JavaScript", blurb: "Declarations and page scripting." },
              { slug: "sql", name: "SQL", blurb: "SELECT, filters, and joins." },
              { slug: "csharp", name: "C#", blurb: "Console apps, vars, and control flow." },
              { slug: "java", name: "Java", blurb: "main, types, and clear loops." },
            ].map((lang) => (
              <li key={lang.slug} className="landing-lang">
                <TrackLogo slug={lang.slug} size="md" title={lang.name} />
                <div>
                  <p className="landing-lang-name">{lang.name}</p>
                  <p className="landing-lang-blurb">{lang.blurb}</p>
                </div>
              </li>
            ))}
          </ul>
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

  const board = tracks;
  const wpm = latestWpm(stats?.wpm_trend);
  const totalExercises = board?.tracks?.reduce((sum, track) => sum + (track.total || 0), 0) || 0;
  const doneExercises =
    board?.tracks?.reduce((sum, track) => sum + (track.completed || 0), 0) ||
    stats?.exercises_completed ||
    0;
  const nextTrack =
    board?.tracks?.find((track) => track.continue_lesson_id) || board?.tracks?.[0] || null;

  return (
    <section className="home-shell rounded-2xl bg-surface p-6 shadow-[var(--shadow)] sm:p-8">
      <div className={reduce ? undefined : "practice-rise"}>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Your practice</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          Welcome back, {user.first_name}
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          {board ? streakNote(board.current_streak_days) : "Loading your practice…"}
        </p>
        <p className="mt-1 text-xs text-muted">
          {user.email} · {user.role.replace("_", " ")}
          {isStaff(user.role) ? " · studio tools unlocked in the nav" : ""}
        </p>
      </div>

      <div className={`home-stats mt-6 ${reduce ? "" : "practice-rise-delay"}`}>
        <StatChip
          label="XP"
          value={(board?.xp ?? stats?.xp ?? 0).toLocaleString()}
          hint="Lessons + games"
        />
        <StatChip
          label="Streak"
          value={
            <span className="inline-flex items-center gap-1.5">
              <StreakFlame days={board?.current_streak_days || 0} />
              {board?.current_streak_days || 0}d
            </span>
          }
          hint={`Best ${board?.longest_streak_days ?? stats?.longest_streak_days ?? 0}d`}
        />
        <StatChip
          label="Exercises"
          value={`${doneExercises}/${totalExercises || "—"}`}
          hint={totalExercises ? `${pct(doneExercises, totalExercises)}% of pool` : "Loading"}
        />
        <StatChip
          label="WPM"
          value={wpm == null ? "—" : wpm}
          hint={stats?.games_played ? `${stats.games_played} game rounds` : "From typed passes"}
        />
      </div>

      {nextTrack?.continue_lesson_id ? (
        <div className={`home-next mt-6 ${reduce ? "" : "practice-rise-delay"}`}>
          <div className="min-w-0">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">Pick up here</p>
            <p className="mt-1 font-medium text-text">
              {nextTrack.name}
              {nextTrack.continue_lesson_title ? ` · ${nextTrack.continue_lesson_title}` : ""}
            </p>
            <p className="mt-1 font-mono text-xs text-muted">
              {(TRACK_META[nextTrack.slug] || {}).sample || "Continue your published path"}
            </p>
          </div>
          <Link
            to={`/learn/lessons/${nextTrack.continue_lesson_id}`}
            className="btn-primary shrink-0"
          >
            Continue lesson
          </Link>
        </div>
      ) : null}

      <div className="mt-6 flex flex-wrap gap-2">
        <Link to="/games" className="btn-secondary">
          Warm up in Games
        </Link>
        <Link to="/playground" className="btn-secondary">
          Open Playground
        </Link>
        <Link to="/projects" className="btn-ghost">
          Projects
        </Link>
        {isSuperAdmin(user.role) ? (
          <Link to="/admin/users" className="btn-ghost">
            Manage users
          </Link>
        ) : null}
      </div>

      <div className="mt-10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Practice tracks</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Beginner basics → intermediate practice → advanced projects. Each card shows where you
              left off and what the track is for.
            </p>
          </div>
        </div>

        {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
        {board === null && !error ? (
          <p className="mt-4 text-sm text-muted">Loading tracks…</p>
        ) : null}
        {board && board.tracks.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No tracks yet. Ask your admin for access.</p>
        ) : null}

        {board && board.tracks.length > 0 ? (
          <ul className="mt-5 grid gap-4">
            {board.tracks.map((track, index) => {
              const meta = TRACK_META[track.slug] || {
                focus: [],
                sample: "",
                tip: track.description,
                level: "Practice path",
              };
              const progress = pct(track.completed, track.total);
              const remaining = Math.max(0, (track.total || 0) - (track.completed || 0));
              const color = track.color || "var(--accent)";
              return (
                <li
                  key={track.slug}
                  className={`home-track ${reduce ? "" : "practice-rise-delay"}`}
                  style={
                    reduce
                      ? { "--track-accent": color }
                      : { "--track-accent": color, animationDelay: `${80 + index * 50}ms` }
                  }
                >
                  <div className="flex flex-wrap items-start gap-4">
                    <TrackLogo slug={track.slug} color={color} size="lg" title={track.name} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold tracking-tight text-text">
                          {track.name}
                        </h3>
                        <span className="home-track-badge">{statusLabel(track.completed, track.total)}</span>
                      </div>
                      <p className="mt-1 text-sm text-muted">{track.description}</p>
                      <p className="mt-1 text-xs text-muted">
                        {meta.level}
                        {meta.tip ? ` · ${meta.tip}` : ""}
                      </p>
                      {meta.focus?.length ? (
                        <ul className="mt-3 flex flex-wrap gap-1.5">
                          {meta.focus.map((item) => (
                            <li key={item} className="home-focus-chip">
                              {item}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {meta.sample ? (
                        <p className="mt-3 font-mono text-xs text-muted">
                          <span className="text-text/80">e.g.</span> {meta.sample}
                        </p>
                      ) : null}
                      <div className="mt-4">
                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                          <span>
                            {track.completed} of {track.total} exercises practiced
                          </span>
                          <span className="font-mono">
                            {progress}% · {remaining} left
                          </span>
                        </div>
                        <div className="home-progress mt-2" aria-hidden>
                          <div className="home-progress-fill" style={{ width: `${progress}%` }} />
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {track.continue_lesson_id ? (
                          <Link
                            to={`/learn/lessons/${track.continue_lesson_id}`}
                            className="btn-primary"
                          >
                            Continue
                            {track.continue_lesson_title
                              ? `: ${track.continue_lesson_title}`
                              : " lesson"}
                          </Link>
                        ) : track.total > 0 && track.completed >= track.total ? (
                          <Link to={`/learn/tracks/${track.slug}`} className="btn-primary">
                            Review track
                          </Link>
                        ) : (
                          <Link to={`/learn/tracks/${track.slug}`} className="btn-primary">
                            Start track
                          </Link>
                        )}
                        <Link to={`/learn/tracks/${track.slug}`} className="btn-secondary">
                          Open outline
                        </Link>
                        <Link to={`/games?track=${track.slug}`} className="btn-ghost">
                          Practice games
                        </Link>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>

      <p className="mt-8 border-t border-muted/15 pt-6 text-sm text-muted">
        Games reuse the same published lines as lessons — hangman, output prediction, and drills keep
        the streak warm without starting a new topic from scratch.
      </p>
    </section>
  );
}
