import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../api/client.js";
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
      <section className="overflow-hidden rounded-2xl bg-surface p-6 shadow-[var(--shadow)] sm:p-8">
        <p className="practice-rise font-mono text-xs uppercase tracking-[0.2em] text-accent">
          Muscle memory for code
        </p>
        <h1 className="practice-rise mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Type the line until your hands know it.
        </h1>
        <p className="practice-rise-delay mt-3 max-w-xl text-sm text-muted sm:text-base">
          Ghostline is a learning path: beginner basics, then intermediate programming, then
          advanced projects — typed with guided hints so the ideas stick.
        </p>
        <p className="practice-rise-delay mt-8 font-mono text-lg sm:text-xl">
          <span>echo </span>
          <span className="ghost-text ghost-breathe">&quot;hello, ghostline&quot;</span>
        </p>
        <div className="practice-rise-delay mt-8 flex flex-wrap gap-3 text-sm">
          <Link to="/demo" className="btn-primary">
            Try a free lesson
          </Link>
          <Link to="/signup" className="btn-secondary">
            Sign up to keep a streak
          </Link>
          <Link to="/login" className="btn-ghost">
            Login
          </Link>
        </div>
        <ul className="practice-rise-delay mt-10 grid gap-4 border-t border-muted/15 pt-8 text-sm text-muted sm:grid-cols-3">
          <li>
            <p className="font-medium text-text">Trace</p>
            <p className="mt-1">Type over ghost text until the shape of the command sticks.</p>
          </li>
          <li>
            <p className="font-medium text-text">Recall</p>
            <p className="mt-1">Write it from memory. That is when the fingers take over.</p>
          </li>
          <li>
            <p className="font-medium text-text">Return</p>
            <p className="mt-1">Streaks and short games keep the skill from going cold.</p>
          </li>
        </ul>
      </section>
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
