import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import StreakFlame from "../../components/feedback/StreakFlame.jsx";

export default function StatsPage() {
  const [stats, setStats] = useState(null);
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/me/stats")
      .then(async (data) => {
        if (cancelled) {
          return;
        }
        setStats(data);
        try {
          const listed = await api("/api/games/leaderboard");
          if (!cancelled) {
            setBoard(listed.entries);
          }
        } catch (err) {
          if (!cancelled && err.status !== 404) {
            setError(err.message);
          }
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

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!stats) {
    return <p className="text-sm text-muted">Loading…</p>;
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Stats</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Streaks, speed, and accuracy — proof the practice is landing in your hands, not only on
        the page.
      </p>
      <p className="mt-4 text-sm text-muted">
        {stats.xp} XP · <StreakFlame days={stats.current_streak_days} />
        {stats.current_streak_days} day streak · longest {stats.longest_streak_days}
      </p>
      <p className="mt-2 text-sm text-muted">
        {stats.exercises_completed} exercises completed · {stats.games_played}{" "}
        {stats.games_played === 1 ? "game round" : "game rounds"}
      </p>
      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <Trend title="WPM" rows={stats.wpm_trend} field="wpm" />
        <Trend title="Accuracy" rows={stats.accuracy_trend} field="accuracy" suffix="%" />
      </div>
      {board ? (
        <div className="mt-8">
          <h2 className="text-lg font-semibold tracking-tight">Leaderboard</h2>
          {board.length === 0 ? (
            <p className="mt-2 text-sm text-muted">No scores yet.</p>
          ) : (
            <ol className="mt-3 flex flex-col gap-2">
              {board.map((entry, index) => (
                <li
                  key={`${entry.name}-${index}`}
                  className="flex flex-wrap justify-between gap-x-3 text-sm"
                >
                  <span>{entry.name}</span>
                  <span className="text-muted">
                    {entry.xp} XP · {entry.streak_days} days
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
      <Link to="/games" className="mt-8 inline-block text-sm text-accent">
        Warm up with a game
      </Link>
    </section>
  );
}

function Trend({ title, rows, field, suffix = "" }) {
  return (
    <div>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-muted">Finish a timed line to start this trend.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.day} className="flex justify-between font-mono text-sm">
              <span className="text-muted">{row.day}</span>
              <span>
                {row[field]}
                {suffix}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
