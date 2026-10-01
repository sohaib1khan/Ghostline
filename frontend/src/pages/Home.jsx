import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../api/client.js";
import StreakFlame from "../components/feedback/StreakFlame.jsx";
import { isStaff, isSuperAdmin } from "../roles.js";

const DOT = {
  bash: "bg-accent",
  python: "bg-accent-2",
  go: "bg-success",
  javascript: "bg-muted",
  sql: "bg-[#c4b4d4]",
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

export default function HomePage() {
  const { user } = useOutletContext();
  const [tracks, setTracks] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) {
      return undefined;
    }
    let cancelled = false;
    api("/api/learn/dashboard")
      .then((data) => {
        if (!cancelled) {
          setTracks(data);
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
        <div className="practice-rise-delay mt-8 flex flex-wrap gap-4 text-sm">
          <Link to="/demo" className="rounded-xl bg-accent px-4 py-2 font-medium text-on-accent">
            Try a free lesson
          </Link>
          <Link to="/signup" className="rounded-xl border border-muted/30 px-4 py-2 text-muted">
            Sign up to keep a streak
          </Link>
          <Link to="/login" className="rounded-xl border border-muted/30 px-4 py-2 text-muted">
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

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)] sm:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">
        Signed in as {user.first_name} {user.last_name}
      </h1>
      <p className="mt-2 text-sm text-muted">
        {user.email} · {user.role}
      </p>
      <p className="mt-4 max-w-2xl text-sm text-muted">
        {tracks ? streakNote(tracks.current_streak_days) : "Loading your practice…"}
      </p>
      <p className="mt-6 font-mono text-lg">
        <span>echo </span>
        <span className="ghost-text ghost-breathe">&quot;keep typing&quot;</span>
      </p>
      {tracks ? (
        <p className="mt-4 text-sm text-muted">
          {tracks.xp} XP · <StreakFlame days={tracks.current_streak_days} />
          {tracks.current_streak_days} day streak
        </p>
      ) : null}
      <div className="mt-8">
        <h2 className="text-lg font-semibold tracking-tight">Practice tracks</h2>
        {isStaff(user.role) ? (
          <p className="mt-2 text-sm text-muted">
            Each track is a path: beginner basics → intermediate practice → advanced projects.{" "}
            <Link to="/projects" className="text-accent">
              Projects
            </Link>
            {isSuperAdmin(user.role) ? (
              <>
                {" "}
                ·{" "}
                <Link to="/admin/users" className="text-accent">
                  Manage users
                </Link>
              </>
            ) : null}
          </p>
        ) : (
          <p className="mt-2 text-sm text-muted">
            Beginner first, then harder ideas with guidance. Open a track — or jump to{" "}
            <Link to="/projects" className="text-accent">
              Projects
            </Link>{" "}
            when you are ready to apply what you typed.
          </p>
        )}
        {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
        {tracks === null && !error ? (
          <p className="mt-4 text-sm text-muted">Loading tracks…</p>
        ) : null}
        {tracks && tracks.tracks.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No tracks yet. Ask your admin for access.</p>
        ) : null}
        {tracks && tracks.tracks.length > 0 ? (
          <ul className="mt-4 flex flex-col gap-3">
            {tracks.tracks.map((track) => (
              <li key={track.slug} className="rounded-xl border border-muted/20 px-4 py-3">
                <p className="flex items-center gap-2 font-medium">
                  <span className={`h-2.5 w-2.5 rounded-full ${DOT[track.slug] || "bg-accent"}`} />
                  {track.name}
                </p>
                <p className="mt-1 text-sm text-muted">{track.description}</p>
                <p className="mt-1 text-sm text-muted">
                  {track.completed} of {track.total} exercises practiced
                </p>
                <div className="mt-2 flex flex-wrap gap-4">
                  {track.continue_lesson_id ? (
                    <Link
                      to={`/learn/lessons/${track.continue_lesson_id}`}
                      className="text-sm text-accent"
                    >
                      Continue
                      {track.continue_lesson_title ? `: ${track.continue_lesson_title}` : ""}
                    </Link>
                  ) : null}
                  <Link to={`/learn/tracks/${track.slug}`} className="text-sm text-accent">
                    Open track
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <p className="mt-8 border-t border-muted/15 pt-6 text-sm text-muted">
        Games are warm-ups for the same lines. Stats show whether the habit is holding.
      </p>
    </section>
  );
}
