import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../api/client.js";
import {
  CertificateDocument,
  DEMO_CERTIFICATE,
} from "../components/certificates/CertificateDocument.jsx";
import TrackLogo from "../components/content/TrackLogo.jsx";
import StreakFlame from "../components/feedback/StreakFlame.jsx";
import { readDailyCounts } from "../lib/dailyGoal.js";
import { readPrefs } from "../prefs.js";
import { isSuperAdmin } from "../roles.js";

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
  const [reviewDue, setReviewDue] = useState(null);
  const [ghostwalkContinue, setGhostwalkContinue] = useState(null);
  const [error, setError] = useState("");
  const prefs = readPrefs();
  const reduce = prefs.reduceMotion;
  const daily = readDailyCounts();
  const goalReviews = prefs.dailyReviews;
  const goalLessons = prefs.dailyLessons;

  useEffect(() => {
    if (!user) {
      return undefined;
    }
    let cancelled = false;
    Promise.all([
      api("/api/learn/dashboard"),
      api("/api/me/stats"),
      api("/api/review/due?limit=20").catch(() => null),
    ])
      .then(([board, meStats, review]) => {
        if (!cancelled) {
          setTracks(board);
          setStats(meStats);
          setReviewDue(review);
          setGhostwalkContinue(board?.ghostwalk || null);
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
            A calm, typing-first path for Bash, Python, Go, JavaScript, SQL, C#, and Java — then
            Ghostwalk mazes, games, and a certificate when your completion rate hits the finish.
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
            <Link to="/signup" className="btn-secondary">
              Create an account
            </Link>
          </div>
          <p className="landing-cta-note">
            Demo needs no account. Sign in later for streaks, Ghostwalk, playground, and certificates.
          </p>
        </section>

        <section className="landing-section" aria-labelledby="landing-path">
          <h2 id="landing-path" className="landing-section-title">
            How the path works
          </h2>
          <p className="landing-section-lead">
            Short lessons on purpose. You type real commands; the server checks the answer string —
            it never runs your code.
          </p>
          <ol className="landing-steps">
            <li>
              <span className="landing-step-num">1</span>
              <div>
                <p className="landing-step-title">Beginner</p>
                <p className="landing-step-body">
                  One-liners until the shape of each command feels familiar.
                </p>
              </div>
            </li>
            <li>
              <span className="landing-step-num">2</span>
              <div>
                <p className="landing-step-title">Intermediate</p>
                <p className="landing-step-body">
                  Guided scripts with hints — daily practice that builds on the basics.
                </p>
              </div>
            </li>
            <li>
              <span className="landing-step-num">3</span>
              <div>
                <p className="landing-step-title">Advanced</p>
                <p className="landing-step-body">
                  Mini-projects typed end to end, then a certificate when the path is complete.
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
              <p className="landing-mode-title">Trace &amp; recall</p>
              <p className="landing-mode-body">
                Type over a guided line, then write it from memory when you are ready.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Ghostwalk</p>
              <p className="landing-mode-body">
                Guide a ghost through Python mazes in the browser — loops, functions, and more.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Games</p>
              <p className="landing-mode-body">
                Short drills reuse published lines — hangman, output prediction, and speed rounds.
              </p>
            </li>
            <li>
              <p className="landing-mode-title">Certificates</p>
              <p className="landing-mode-body">
                Track your completion rate. Finish every exercise and module boss to unlock a
                printable award with your name.
              </p>
            </li>
          </ul>
        </section>

        <section className="landing-section landing-section-langs" aria-labelledby="landing-langs">
          <h2 id="landing-langs" className="landing-section-title">
            Languages on the path
          </h2>
          <p className="landing-section-lead">
            Start in the free demo, or unlock the full ladder when you create an account.
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

        <section className="landing-section" aria-labelledby="landing-certificate">
          <div className="landing-cert-layout">
            <div>
              <h2 id="landing-certificate" className="landing-section-title">
                Finish a path. Earn the certificate.
              </h2>
              <p className="landing-section-lead">
                Progress is visible as you go. When your completion rate hits 100% — every exercise
                and every module boss — the watermark drops and your profile name is on the award.
              </p>
              <div className="landing-cta">
                <Link to="/demo" className="btn-primary">
                  Try a free lesson
                </Link>
                <Link to="/signup" className="btn-secondary">
                  Sign up to earn yours
                </Link>
              </div>
            </div>
            <div className="landing-certificate-demo">
              <CertificateDocument
                cert={DEMO_CERTIFICATE}
                forceWatermark
                watermarkLabel="Demo"
                watermarkHint="Sign in · finish a path · unlock yours"
              />
            </div>
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

  const board = tracks;
  const wpm = latestWpm(stats?.wpm_trend);
  const totalExercises = board?.tracks?.reduce((sum, track) => sum + (track.total || 0), 0) || 0;
  const doneExercises =
    board?.tracks?.reduce((sum, track) => sum + (track.completed || 0), 0) ||
    stats?.exercises_completed ||
    0;
  const resume = board?.continue || null;
  const nextTrack = resume
    ? board?.tracks?.find((track) => track.slug === resume.track_slug) || {
        slug: resume.track_slug,
        name: resume.track_name,
        continue_lesson_id: resume.lesson_id,
        continue_lesson_title: resume.lesson_title,
      }
    : board?.tracks?.find((track) => track.continue_lesson_id) || board?.tracks?.[0] || null;
  const continueLessonId = resume?.lesson_id || nextTrack?.continue_lesson_id || null;
  const continueLessonTitle = resume?.lesson_title || nextTrack?.continue_lesson_title || null;
  const continueTrackName = resume?.track_name || nextTrack?.name || "";
  const continueTrackSlug = resume?.track_slug || nextTrack?.slug || "";

  const reviewCount = reviewDue?.count || 0;
  const reviewsDone = Math.min(daily.reviews, goalReviews || 0);
  const lessonsDone = Math.min(daily.lessons, goalLessons || 0);

  return (
    <section className="home-shell rounded-2xl bg-surface p-5 shadow-[var(--shadow)] sm:p-8">
      <header className={`home-hero ${reduce ? "" : "practice-rise"}`}>
        <div className="min-w-0">
          <p className="home-kicker">Ghostline</p>
          <h1 className="home-title">Welcome back, {user.first_name}</h1>
          <p className="home-lead">
            {board ? streakNote(board.current_streak_days) : "Loading your practice…"}
          </p>
        </div>
        {goalReviews > 0 || goalLessons > 0 ? (
          <div className="home-daily" role="status" aria-label="Daily goal progress">
            <p className="home-daily-title">Today&apos;s goal</p>
            <ul className="home-daily-meters">
              {goalReviews > 0 ? (
                <li>
                  <div className="home-daily-row">
                    <span>
                      Reviews {reviewsDone}/{goalReviews}
                    </span>
                    <span className="font-mono">{pct(reviewsDone, goalReviews)}%</span>
                  </div>
                  <div className="home-progress" aria-hidden>
                    <div
                      className="home-progress-fill"
                      style={{ width: `${pct(reviewsDone, goalReviews)}%` }}
                    />
                  </div>
                </li>
              ) : null}
              {goalLessons > 0 ? (
                <li>
                  <div className="home-daily-row">
                    <span>
                      Lessons {lessonsDone}/{goalLessons}
                    </span>
                    <span className="font-mono">{pct(lessonsDone, goalLessons)}%</span>
                  </div>
                  <div className="home-progress" aria-hidden>
                    <div
                      className="home-progress-fill"
                      style={{ width: `${pct(lessonsDone, goalLessons)}%` }}
                    />
                  </div>
                </li>
              ) : null}
            </ul>
          </div>
        ) : null}
      </header>

      <div className={`home-stats ${reduce ? "" : "practice-rise-delay"}`} aria-label="Your stats">
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

      <section className="home-jump" aria-labelledby="home-jump-title">
        <div className="home-section-head">
          <h2 id="home-jump-title" className="home-section-title">
            Jump back in
          </h2>
          <p className="home-section-lead">Pick one path — reviews, a lesson, or Ghostwalk.</p>
        </div>
        <ul className="home-jump-grid">
          {reviewCount > 0 ? (
            <li className="home-jump-card home-jump-card-review">
              <p className="home-jump-label">Review</p>
              <p className="home-jump-heading">{reviewCount} due now</p>
              <p className="home-jump-copy">
                About {reviewDue.estimate_minutes || 1} min · keep commands warm
              </p>
              <Link to="/review" className="btn-primary home-jump-cta">
                Start reviews
              </Link>
            </li>
          ) : null}

          {continueLessonId ? (
            <li className="home-jump-card home-jump-card-lesson">
              <p className="home-jump-label">Lesson</p>
              <p className="home-jump-heading">
                {continueTrackName}
                {continueLessonTitle ? ` · ${continueLessonTitle}` : ""}
              </p>
              <p className="home-jump-copy font-mono">
                {(TRACK_META[continueTrackSlug] || {}).sample || "Continue your published path"}
              </p>
              <Link to={`/learn/lessons/${continueLessonId}`} className="btn-primary home-jump-cta">
                Continue lesson
              </Link>
            </li>
          ) : null}

          <li className="home-jump-card home-jump-card-ghostwalk">
            <p className="home-jump-label">Ghostwalk</p>
            <p className="home-jump-heading">
              {ghostwalkContinue
                ? ghostwalkContinue.label.replace(/^Ghostwalk · /, "")
                : "Python maze levels"}
            </p>
            <p className="home-jump-copy">Guide the ghost with real Python in your browser.</p>
            <Link
              to={ghostwalkContinue ? `/ghostwalk/${ghostwalkContinue.slug}` : "/ghostwalk"}
              className="btn-primary home-jump-cta"
            >
              {ghostwalkContinue ? "Continue Ghostwalk" : "Open Ghostwalk"}
            </Link>
          </li>
        </ul>
      </section>

      <nav className="home-also" aria-label="Other practice tools">
        <p className="home-also-label">Also</p>
        <div className="home-also-links">
          <Link to="/games" className="home-also-link">
            Games
          </Link>
          <Link to="/playground" className="home-also-link">
            Playground
          </Link>
          <Link to="/projects" className="home-also-link">
            Projects
          </Link>
          <Link to="/ghostwalk" className="home-also-link">
            Ghostwalk map
          </Link>
          {isSuperAdmin(user.role) ? (
            <Link to="/admin/users" className="home-also-link">
              Users
            </Link>
          ) : null}
        </div>
      </nav>

      <div className="home-tracks">
        <div className="home-section-head">
          <h2 className="home-section-title">Practice tracks</h2>
          <p className="home-section-lead">
            Beginner → intermediate → advanced. Open a track to see modules and pick up where you
            left off.
          </p>
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
                            {track.review_due ? ` · ${track.review_due} due for review` : ""}
                            {track.retention_pct != null
                              ? ` · ${track.retention_pct}% retention`
                              : ""}
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

      <p className="home-footnote">
        Games reuse the same published lines as lessons — short drills keep the streak warm without
        starting a new topic.
      </p>
    </section>
  );
}
