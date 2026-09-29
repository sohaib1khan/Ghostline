import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { readPrefs } from "../../prefs.js";

export default function GamesPage() {
  const [catalog, setCatalog] = useState(null);
  const [slug, setSlug] = useState("");
  const [rounds, setRounds] = useState(10);
  const [error, setError] = useState("");
  const reduce = readPrefs().reduceMotion;

  useEffect(() => {
    let cancelled = false;
    api("/api/games/catalog")
      .then((data) => {
        if (!cancelled) {
          setCatalog(data);
          setSlug(data.tracks[0]?.slug || "");
          setRounds(data.default_session_rounds || 10);
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
  if (!catalog) {
    return <p className="text-sm text-muted">Loading…</p>;
  }

  const selected = catalog.tracks.find((track) => track.slug === slug) || null;

  return (
    <section className="overflow-hidden rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <div className={reduce ? undefined : "practice-rise"}>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">Practice arena</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Games</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Every round pulls from your <span className="text-text">published</span> lessons on this
          track — including everything you imported. Pool size is the limit; pick how many rounds
          you want today.
        </p>
      </div>
      {catalog.tracks.length === 0 ? (
        <p className="mt-4 text-sm text-muted">No tracks yet. Ask your admin for access.</p>
      ) : (
        <div className={`mt-6 flex flex-wrap gap-2 ${reduce ? "" : "practice-rise-delay"}`}>
          {catalog.tracks.map((track) => (
            <button
              key={track.slug}
              type="button"
              onClick={() => setSlug(track.slug)}
              className={`rounded-full border px-4 py-2 text-sm transition ${
                track.slug === slug
                  ? "border-accent bg-accent text-on-accent"
                  : "border-muted/30 text-muted hover:border-accent/50"
              }`}
            >
              {track.name}
              <span className="ml-2 font-mono text-xs opacity-80">
                {track.pools ? Object.values(track.pools).reduce((a, b) => a + b, 0) : 0}
              </span>
            </button>
          ))}
        </div>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
        <label className="text-muted">
          Session length
          <select
            className="ml-2 rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            value={rounds}
            onChange={(event) => setRounds(Number(event.target.value))}
            aria-label="Session length"
          >
            {[5, 10, 15, 20, 30].map((n) => (
              <option key={n} value={n}>
                {n} rounds
              </option>
            ))}
            <option value={999}>Until I stop</option>
          </select>
        </label>
        {selected ? (
          <p className="text-muted">
            Published pool on {selected.name}:{" "}
            <span className="font-mono text-text">
              {selected.pools
                ? Object.entries(selected.pools)
                    .map(([id, count]) => `${count}`)
                    .join(" · ")
                : "0"}
            </span>
          </p>
        ) : null}
      </div>
      <ul className="mt-6 grid gap-3 md:grid-cols-2">
        {catalog.games.map((game, index) => {
          const pool = selected?.pools?.[game.id] || 0;
          const playable = Boolean(slug) && pool > 0;
          const session = Math.min(rounds, Math.max(pool, 1));
          return (
            <li
              key={game.id}
              className={`game-card rounded-xl border border-muted/20 px-4 py-4 ${
                reduce ? "" : "practice-rise-delay"
              }`}
              style={reduce ? undefined : { animationDelay: `${80 + index * 60}ms` }}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium">{game.name}</p>
                <span className="font-mono text-xs text-muted">{pool} ready</span>
              </div>
              <p className="mt-1 text-sm text-muted">{game.blurb}</p>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/20">
                <div
                  className="pool-fill h-full rounded-full bg-accent"
                  style={{ width: `${Math.min(100, pool ? 12 + Math.min(pool, 40) * 2 : 0)}%` }}
                />
              </div>
              {playable ? (
                <Link
                  to={`/games/${game.id}?track=${slug}&rounds=${session}`}
                  className="mt-3 inline-block text-sm text-accent"
                >
                  Play {session} round{session === 1 ? "" : "s"}
                </Link>
              ) : (
                <p className="mt-3 text-sm text-muted">
                  {slug
                    ? "No published exercises fit this game on this track yet."
                    : "Pick a track."}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
