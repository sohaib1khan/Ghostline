import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client.js";
import StreakFlame from "../../components/feedback/StreakFlame.jsx";

const SORTS = [
  { id: "xp", label: "XP" },
  { id: "time_spent_seconds", label: "Total time" },
  { id: "lesson_time_seconds", label: "Lesson time" },
  { id: "game_time_seconds", label: "Game time" },
  { id: "time_spent_7d", label: "Time (7d)" },
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
  ghost_race: "Ghost race",
  code_hangman: "Code hangman",
  codele: "Codele",
  memory_match: "Memory match",
  code_crossword: "Code crossword",
  tic_tac_toe: "Tic-tac-toe",
  syntax_snake: "Syntax snake",
  predict_output: "Predict output",
  code_scramble: "Code scramble",
  query_detective: "Query detective",
  boss_battle: "Boss battle",
};

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  if (total < 60) {
    return `${total}s`;
  }
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours === 0) {
    return secs && minutes < 10 ? `${minutes}m ${secs}s` : `${minutes}m`;
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
  const [sort, setSort] = useState("time_spent_seconds");
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
          const hay = `${row.first_name} ${row.last_name} ${row.role}`.toLowerCase();
          return hay.includes(needle);
        })
      : data.leaderboard;
    return [...filtered].sort((left, right) => {
      const delta = (right[sort] || 0) - (left[sort] || 0);
      if (delta !== 0) {
        return delta;
      }
      return (right.time_spent_seconds || 0) - (left.time_spent_seconds || 0);
    });
  }, [data, query, sort]);

  const topByTime = useMemo(() => {
    if (!data?.leaderboard) {
      return [];
    }
    return [...data.leaderboard]
      .filter((row) => (row.time_spent_seconds || 0) > 0)
      .sort((left, right) => (right.time_spent_seconds || 0) - (left.time_spent_seconds || 0))
      .slice(0, 5);
  }, [data]);

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }
  if (!data) {
    return <p className="text-sm text-muted">Loading Leaderboard…</p>;
  }

  const summary = data.summary;
  const maxEvents = Math.max(1, ...data.activity.map((day) => day.events));
  const maxSeconds = Math.max(1, ...data.activity.map((day) => day.seconds || 0));
  const sourceTotal = Math.max(1, data.sources.reduce((sum, row) => sum + row.count, 0));
  const sourceTimeTotal = Math.max(
    1,
    data.sources.reduce((sum, row) => sum + (row.seconds || 0), 0),
  );
  const lessonShare = summary.time_spent_seconds
    ? Math.round((summary.lesson_time_seconds / summary.time_spent_seconds) * 100)
    : 0;
  const gameShare = summary.time_spent_seconds
    ? Math.round((summary.game_time_seconds / summary.time_spent_seconds) * 100)
    : 0;

  return (
    <section className="flex flex-col gap-6">
      <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Studio</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Leaderboard</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Usage dashboard for every approved learner — XP, streaks, and time spent typing in lessons
          and games.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Learners" value={summary.approved_users} />
          <Metric label="Active in 7 days" value={summary.active_learners_7d} />
          <Metric label="Total XP" value={summary.total_xp.toLocaleString()} />
          <Metric label="Average WPM" value={summary.avg_wpm == null ? "—" : summary.avg_wpm} />
          <Metric label="Exercises done" value={summary.exercises_completed.toLocaleString()} />
          <Metric label="Done this week" value={summary.exercises_completed_7d} />
          <Metric label="Practice sessions" value={summary.practice_sessions.toLocaleString()} />
          <Metric label="Pending signups" value={summary.pending_users} />
        </div>
      </div>

      <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Usage · time on task</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Captured from typed lesson checks and game rounds. Duration is counted on every
              attempt, not only passes.
            </p>
          </div>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Total learning time"
            value={formatDuration(summary.time_spent_seconds)}
            hint="Lessons + games"
          />
          <Metric
            label="Lesson typing"
            value={formatDuration(summary.lesson_time_seconds)}
            hint={summary.time_spent_seconds ? `${lessonShare}% of total` : "No time yet"}
          />
          <Metric
            label="Game practice"
            value={formatDuration(summary.game_time_seconds)}
            hint={summary.time_spent_seconds ? `${gameShare}% of total` : "No time yet"}
          />
          <Metric
            label="Last 7 days"
            value={formatDuration(summary.time_spent_7d)}
            hint="All practice sources"
          />
        </div>
        <div className="mt-5">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>Lesson vs games</span>
            <span className="font-mono">
              {formatDuration(summary.lesson_time_seconds)} ·{" "}
              {formatDuration(summary.game_time_seconds)}
            </span>
          </div>
          <div className="leaderboard-split mt-2" aria-hidden>
            <div
              className="leaderboard-split-lesson"
              style={{ width: `${Math.max(summary.time_spent_seconds ? lessonShare : 0, 0)}%` }}
            />
            <div
              className="leaderboard-split-game"
              style={{ width: `${Math.max(summary.time_spent_seconds ? gameShare : 0, 0)}%` }}
            />
          </div>
        </div>
        {topByTime.length ? (
          <div className="mt-6">
            <h3 className="text-sm font-medium text-text">Most time on task</h3>
            <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              {topByTime.map((row, index) => (
                <li key={row.id} className="leaderboard-top-time">
                  <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
                    #{index + 1}
                  </p>
                  <p className="mt-1 truncate font-medium text-text">
                    {row.first_name} {row.last_name}
                  </p>
                  <p className="mt-1 font-mono text-sm text-accent">
                    {formatDuration(row.time_spent_seconds)}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    L {formatDuration(row.lesson_time_seconds)} · G{" "}
                    {formatDuration(row.game_time_seconds)}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="mt-6 text-sm text-muted">
            No timed practice yet. Time fills in as learners check lessons and play games.
          </p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
          <h2 className="text-lg font-semibold tracking-tight">Activity · 14 days</h2>
          <p className="mt-1 text-sm text-muted">Events each day, with time spent under the bars.</p>
          <div className="leaderboard-bars mt-5" role="img" aria-label="Daily practice activity">
            {data.activity.map((day) => (
              <div
                key={day.day}
                className="leaderboard-bar-col"
                title={`${day.day}: ${day.events} events · ${formatDuration(day.seconds)}`}
              >
                <div
                  className="leaderboard-bar"
                  style={{ height: `${Math.max(6, Math.round((day.events / maxEvents) * 100))}%` }}
                />
                <div
                  className="leaderboard-bar-time"
                  style={{
                    height: `${Math.max(4, Math.round(((day.seconds || 0) / maxSeconds) * 100))}%`,
                  }}
                />
                <span className="leaderboard-bar-label">{formatDay(day.day)}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className="leaderboard-legend leaderboard-legend-events" /> Events
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="leaderboard-legend leaderboard-legend-time" /> Time
            </span>
          </p>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {data.activity
              .filter((day) => day.events > 0 || day.seconds > 0)
              .slice(-4)
              .reverse()
              .map((day) => (
                <li key={`detail-${day.day}`} className="font-mono text-xs text-muted">
                  {formatDay(day.day)} · {day.events} events · {day.learners} learners ·{" "}
                  {formatDuration(day.seconds)}
                  {day.lesson_seconds || day.game_seconds
                    ? ` (L ${formatDuration(day.lesson_seconds)} / G ${formatDuration(day.game_seconds)})`
                    : ""}
                </li>
              ))}
          </ul>
        </div>

        <div className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
          <h2 className="text-lg font-semibold tracking-tight">Practice mix</h2>
          <p className="mt-1 text-sm text-muted">Sessions and time by source.</p>
          {data.sources.length === 0 ? (
            <p className="mt-4 text-sm text-muted">No practice yet.</p>
          ) : (
            <ul className="mt-5 flex flex-col gap-3">
              {data.sources.map((row) => (
                <li key={row.source}>
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span>{SOURCE_LABELS[row.source] || row.source}</span>
                    <span className="font-mono text-muted">
                      {row.count} · {formatDuration(row.seconds)}
                    </span>
                  </div>
                  <div className="leaderboard-track mt-1">
                    <div
                      className="leaderboard-track-fill"
                      style={{
                        width: `${Math.round(
                          ((row.seconds || row.count) /
                            (row.seconds ? sourceTimeTotal : sourceTotal)) *
                            100,
                        )}%`,
                      }}
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
              Ranked board with usage. Sort by total, lesson, or game time to see who is practicing.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm text-muted" htmlFor="leaderboard-search">
              Search
              <input
                id="leaderboard-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Name"
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
            <table className="leaderboard-table w-full min-w-[64rem] text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-[0.12em] text-muted">
                  <th scope="col">#</th>
                  <th scope="col">Learner</th>
                  <th scope="col">XP</th>
                  <th scope="col">Streak</th>
                  <th scope="col">Exercises</th>
                  <th scope="col">Games</th>
                  <th scope="col">Sessions</th>
                  <th scope="col">Total time</th>
                  <th scope="col">Lessons</th>
                  <th scope="col">Games time</th>
                  <th scope="col">7d</th>
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
                      {row.role !== "learner" ? (
                        <p className="text-xs text-muted">{row.role}</p>
                      ) : null}
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
                    <td className="font-mono font-medium text-text">
                      {formatDuration(row.time_spent_seconds)}
                    </td>
                    <td className="font-mono">{formatDuration(row.lesson_time_seconds)}</td>
                    <td className="font-mono">{formatDuration(row.game_time_seconds)}</td>
                    <td className="font-mono">{formatDuration(row.time_spent_7d)}</td>
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

function Metric({ label, value, hint }) {
  return (
    <div className="leaderboard-metric">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
