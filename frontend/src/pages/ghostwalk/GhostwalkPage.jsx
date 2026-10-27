import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { GHOSTWALK_LANGUAGES } from "../../ghostwalk/languages.js";
import { GHOSTWALK_GAMES, gameMeta } from "../../ghostwalk/themes.js";

function LevelCard({ level, badge }) {
  return (
    <li className="rounded-xl border border-muted/20 bg-bg/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-wider text-accent">
            {badge || `Level ${level.order}`}
          </p>
          <h2 className="mt-1 text-lg font-semibold">{level.title}</h2>
          <p className="mt-1 text-sm text-muted">{level.concept}</p>
        </div>
        <p className="font-mono text-sm" aria-label={`${level.stars} of 3 stars`}>
          {"★".repeat(level.stars)}
          {"☆".repeat(3 - level.stars)}
        </p>
      </div>
      {level.unlocked ? (
        <Link
          to={`/ghostwalk/${level.slug}`}
          className="mt-3 inline-flex min-h-11 items-center rounded-xl bg-accent px-4 text-sm font-medium text-on-accent"
        >
          {level.completed ? "Replay" : "Play"}
        </Link>
      ) : (
        <p className="mt-3 text-sm text-muted" role="status">
          Locked — {level.lock_reason || "Solve the previous level first."}
        </p>
      )}
    </li>
  );
}

export default function GhostwalkPage() {
  const [language, setLanguage] = useState("python");
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    api(`/api/ghostwalk/levels?language=${encodeURIComponent(language)}`)
      .then((data) => {
        if (!cancelled) setBoard(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [language]);

  const available = GHOSTWALK_LANGUAGES.filter(
    (item) => !board?.languages?.length || board.languages.includes(item.id),
  );
  const meta = gameMeta(language);

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Ghostwalk</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Choose a game</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Each language is its own world — ghost, story, and idioms. Code runs in your browser; the
        server only replays your moves.
      </p>

      <ul className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Ghostwalk games">
        {GHOSTWALK_GAMES.filter((game) => available.some((item) => item.id === game.id)).map(
          (game) => {
            const active = language === game.id;
            const solved =
              board && board.language === game.id
                ? `${board.solved} of ${board.total} solved`
                : active && board
                  ? `${board.solved} of ${board.total} solved`
                  : "Open path";
            return (
              <li key={game.id}>
                <button
                  type="button"
                  aria-pressed={active}
                  className={[
                    "flex min-h-[7.5rem] w-full flex-col rounded-2xl border-2 p-4 text-left transition",
                    active
                      ? "border-accent bg-accent/15"
                      : "border-muted/25 bg-bg/40 hover:border-accent/50",
                  ].join(" ")}
                  onClick={() => setLanguage(game.id)}
                >
                  <p className="font-mono text-[11px] uppercase tracking-wider text-accent">
                    {GHOSTWALK_LANGUAGES.find((item) => item.id === game.id)?.label || game.id}
                  </p>
                  <p className="mt-1 text-lg font-semibold">{game.game}</p>
                  <p className="mt-1 text-sm text-muted">
                    Ghost: {game.ghost} · {game.blurb}
                  </p>
                  <p className="mt-auto pt-3 font-mono text-xs text-muted">
                    {active && board ? solved : "Select to load progress"}
                  </p>
                </button>
              </li>
            );
          },
        )}
      </ul>

      {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
      {!board && !error ? <p className="mt-4 text-sm text-muted">Loading levels…</p> : null}
      {board ? (
        <>
          <div className="mt-10">
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
              {meta.game} · {meta.ghost}
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight">Level map</h2>
            <p className="mt-2 font-mono text-sm text-muted" role="status">
              {board.solved} of {board.total} solved · {board.stars_earned} of {board.stars_total}{" "}
              stars
            </p>
            <ol className="mt-4 grid gap-3 sm:grid-cols-2">
              {(board.levels || []).map((level) => (
                <LevelCard key={level.slug} level={level} />
              ))}
            </ol>
          </div>

          {(board.farm || []).length ? (
            <div className="mt-10">
              <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Ghostfarm</p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight">Interactive farm plots</h2>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                Plant on soil (~), water seeds, harvest ripe crops, and deliver to the barn (B).
              </p>
              <p className="mt-3 font-mono text-sm text-muted" role="status">
                {board.farm_solved} of {board.farm_total} plots · {board.farm_stars_earned} of{" "}
                {board.farm_stars_total} stars
              </p>
              <ol className="mt-4 grid gap-3 sm:grid-cols-2">
                {(board.farm || []).map((level) => (
                  <LevelCard key={level.slug} level={level} badge="Farm" />
                ))}
              </ol>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
