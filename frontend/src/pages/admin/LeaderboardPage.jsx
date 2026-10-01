import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client.js";
import StreakFlame from "../../components/feedback/StreakFlame.jsx";

const SORTS = [
  { id: "xp", label: "XP" },
  { id: "time_spent_seconds", label: "Time" },
  { id: "exercises_completed", label: "Exercises" },
  { id: "current_streak_days", label: "Streak" },
  { id: "practice_sessions", label: "Sessions" },
];

const SOURCE_LABELS = {
  lesson: "Lessons",
  speed_drill: "Speed drill",
  bug_hunt: "Bug hunt",
  command_roulette: "Command roulette",
  fill_frenzy: "Fill frenzy",
};

function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  if (total < 60) {
    return `${total}s`;
  }
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours === 0) {
    return `${minutes}m`;
  }
  if (minutes === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${minutes}m`;
}

function formatDay(iso) {
  if (!iso) {
    return "—";
  }
  const date = new Date(`${iso}T12:00:00`);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatWhen(iso) {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso.slice(0, 10);
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function LeaderboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [sort, setSort] = useState("xp");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/admin/insights")
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
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
  }, []);

  const ranked = useMemo(() => {
    if (!data?.leaderboard) {
      return [];
    }
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? data.leaderboard.filter((row) => {
          const hay = `${row.first_name} ${row.last_name} ${row.email} ${row.role}`.toLowerCase();
          return hay.includes(needle);
        })
      : data.leaderboard;
    return [...filtered].sort((left, right) => {
      const delta = (right[sort] || 0) - (left[sort] || 0);
      if (delta !== 0) {
        return delta;
      }
      return (right.xp || 0) - (left.xp || 0);
    });
  }, [data, query, sort]);

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!data) {
    return <p className="text-sm text-muted">Loading Leaderboard…</p>;
  }

  const summary = data.summary;
  const maxEvents = Math.max(1, ...data.activity.map((day) => day.events));
  const sourceTotal = Math.max(1, data.sources.reduce((sum, row) => sum + row.count, 0));

  return (
    <section className="flex flex-col gap-6">
      <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Studio</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Leaderboard</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Every approved learner’s practice — XP, streaks, sessions, and time spent typing.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Learners" value={summary.approved_users} />
          <Metric label="Active in 7 days" value={summary.active_learners_7d} />
          <Metric label="Total XP" value={summary.total_xp.toLocaleString()} />
          <Metric label="Time tracked" value={formatDuration(summary.time_spent_seconds)} />
          <Metric label="Exercises done" value={summary.exercises_completed.toLocaleString()} />
          <Metric label="Done this week" value={summary.exercises_completed_7d} />
          <Metric label="Practice sessions" value={summary.practice_sessions.toLocaleString()} />
          <Metric
            label="Average WPM"
            value={summary.avg_wpm == null ? "—" : summary.avg_wpm}
          />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
          <h2 className="text-lg font-semibold tracking-tight">Activity · 14 days</h2>
          <p className="mt-1 text-sm text-muted">Practice events and learners each day.</p>
          <div className="leaderboard-bars mt-5" role="img" aria-label="Daily practice activity">
            {data.activity.map((day) => (
              <div key={day.day} className="leaderboard-bar-col" title={`${day.day}: ${day.events} events`}>
                <div
                  className="leaderboard-bar"
                  style={{ height: `${Math.max(6, Math.round((day.events / maxEvents) * 100))}%` }}
                />
                <span className="leaderboard-bar-label">{formatDay(day.day)}</span>
              </div>
            ))}
          </div>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {data.activity
              .filter((day) => day.events > 0)
              .slice(-4)
              .reverse()
              .map((day) => (
                <li key={`detail-${day.day}`} className="font-mono text-xs text-muted">
                  {formatDay(day.day)} · {day.events} events · {day.learners} learners ·{" "}
                  {formatDuration(day.seconds)}
                </li>
              ))}
          </ul>
        </div>

        <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
          <h2 className="text-lg font-semibold tracking-tight">Practice mix</h2>
          <p className="mt-1 text-sm text-muted">Where sessions come from.</p>
          {data.sources.length === 0 ? (
            <p className="mt-4 text-sm text-muted">No practice yet.</p>
          ) : (
            <ul className="mt-5 flex flex-col gap-3">
              {data.sources.map((row) => (
                <li key={row.source}>
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span>{SOURCE_LABELS[row.source] || row.source}</span>
                    <span className="font-mono text-muted">{row.count}</span>
                  </div>
                  <div className="leaderboard-track mt-1">
                    <div
                      className="leaderboard-track-fill"
                      style={{ width: `${Math.round((row.count / sourceTotal) * 100)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Learners</h2>
            <p className="mt-1 text-sm text-muted">
              Ranked board with usage. Time spent fills in as people finish new exercises.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm text-muted" htmlFor="leaderboard-search">
              Search
              <input
                id="leaderboard-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Name or email"
                className="mt-1 block min-w-48 rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
              />
            </label>
            <label className="text-sm text-muted" htmlFor="leaderboard-sort">
              Sort
              <select
                id="leaderboard-sort"
                value={sort}
                onChange={(event) => setSort(event.target.value)}
                className="mt-1 block rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
              >
                {SORTS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {ranked.length === 0 ? (
          <p className="mt-6 text-sm text-muted">No matching learners.</p>
        ) : (
          <div className="mt-6 overflow-x-auto">
            <table className="leaderboard-table w-full min-w-[52rem] text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-[0.12em] text-muted">
                  <th scope="col">#</th>
                  <th scope="col">Learner</th>
                  <th scope="col">XP</th>
                  <th scope="col">Streak</th>
                  <th scope="col">Exercises</th>
                  <th scope="col">Games</th>
                  <th scope="col">Sessions</th>
                  <th scope="col">Time</th>
                  <th scope="col">Avg WPM</th>
                  <th scope="col">Last practice</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((row, index) => (
                  <tr key={row.id}>
                    <td className="font-mono text-muted">{index + 1}</td>
                    <td>
                      <p className="font-medium text-text">
                        {row.first_name} {row.last_name}
                      </p>
                      <p className="break-all text-xs text-muted">
                        {row.email}
                        {row.role !== "learner" ? ` · ${row.role}` : ""}
                      </p>
                    </td>
                    <td className="font-mono">{row.xp.toLocaleString()}</td>
                    <td>
                      <span className="inline-flex items-center gap-1">
                        <StreakFlame days={row.current_streak_days} />
                        <span className="font-mono">{row.current_streak_days}</span>
                      </span>
                      <span className="mt-1 block text-xs text-muted">
                        best {row.longest_streak_days}
                      </span>
                    </td>
                    <td className="font-mono">{row.exercises_completed}</td>
                    <td className="font-mono">{row.games_played}</td>
                    <td className="font-mono">{row.practice_sessions}</td>
                    <td className="font-mono">{formatDuration(row.time_spent_seconds)}</td>
                    <td className="font-mono">{row.avg_wpm == null ? "—" : row.avg_wpm}</td>
                    <td className="text-muted">{formatWhen(row.last_practice_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="leaderboard-metric">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text">{value}</p>
    </div>
  );
}
