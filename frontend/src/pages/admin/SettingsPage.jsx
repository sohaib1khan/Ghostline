import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";
import { isSuperAdmin } from "../../roles.js";
import { useOutletContext } from "react-router-dom";

const EMPTY_TRACKS = [
  { title: "Dawn", url: "/sounds/music/calm-01-dawn.wav" },
  { title: "Harbor", url: "/sounds/music/calm-02-harbor.wav" },
  { title: "Mist", url: "/sounds/music/calm-03-mist.wav" },
  { title: "Ember", url: "/sounds/music/calm-04-ember.wav" },
  { title: "Tide", url: "/sounds/music/calm-05-tide.wav" },
];

export default function SettingsPage() {
  const { user } = useOutletContext();
  const superAdmin = isSuperAdmin(user?.role);
  const [enabled, setEnabled] = useState(false);
  const [musicEnabled, setMusicEnabled] = useState(true);
  const [rotate, setRotate] = useState(true);
  const [tracks, setTracks] = useState(EMPTY_TRACKS);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api("/api/admin/settings"),
      superAdmin ? api("/api/music/playlist").catch(() => null) : Promise.resolve(null),
    ])
      .then(([settings, playlist]) => {
        if (cancelled) return;
        setEnabled(settings.leaderboard_enabled);
        if (playlist) {
          setMusicEnabled(playlist.enabled !== false);
          setRotate(playlist.rotate !== false);
          const next = (playlist.tracks || []).map((track, index) => ({
            title: track.title || EMPTY_TRACKS[index]?.title || `Track ${index + 1}`,
            url: track.url || EMPTY_TRACKS[index]?.url || "",
          }));
          while (next.length < 5) {
            next.push({ ...EMPTY_TRACKS[next.length] });
          }
          setTracks(next.slice(0, 5));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [superAdmin]);

  async function saveLeaderboard(event) {
    event.preventDefault();
    setPending(true);
    setNotice("");
    setError("");
    try {
      const data = await api("/api/admin/settings", {
        method: "PUT",
        body: { leaderboard_enabled: enabled },
      });
      setEnabled(data.leaderboard_enabled);
      setNotice("Leaderboard settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function saveMusic(event) {
    event.preventDefault();
    if (!superAdmin) return;
    setPending(true);
    setNotice("");
    setError("");
    try {
      const data = await api("/api/admin/music/playlist", {
        method: "PUT",
        body: {
          enabled: musicEnabled,
          rotate,
          tracks,
        },
      });
      setMusicEnabled(data.enabled !== false);
      setRotate(data.rotate !== false);
      setTracks(
        (data.tracks || []).map((track) => ({
          title: track.title || "",
          url: track.url || "",
        })),
      );
      setNotice("Music playlist saved. Learners hear the new tracks after refresh.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  function updateTrack(index, patch) {
    setTracks((current) =>
      current.map((track, i) => (i === index ? { ...track, ...patch } : track)),
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold tracking-tight">Leaderboard</h1>
        <p className="mt-2 text-sm text-muted">Site-wide visibility for learner XP.</p>
        <form className="mt-6 flex max-w-md flex-col gap-5" onSubmit={saveLeaderboard}>
          <label className="flex items-center gap-2 text-sm" htmlFor="leaderboard">
            <input
              id="leaderboard"
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            Show the leaderboard
          </label>
          <p className="text-sm text-muted">
            When this is on, learners see public aliases and XP. Real names stay private.
          </p>
          <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save leaderboard"}</SubmitButton>
        </form>
      </section>

      {superAdmin ? (
        <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
          <h2 className="text-2xl font-semibold tracking-tight">Calm music</h2>
          <p className="mt-2 text-sm text-muted">
            Up to five soft tracks rotate while learners practice. Use the built-in pads or paste
            your own URLs (mp3/wav under this site or https).
          </p>
          <form className="mt-6 flex flex-col gap-5" onSubmit={saveMusic}>
            <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="music-enabled">
              <input
                id="music-enabled"
                type="checkbox"
                checked={musicEnabled}
                onChange={(event) => setMusicEnabled(event.target.checked)}
              />
              Music playlist available to learners
            </label>
            <label className="flex min-h-11 items-center gap-2 text-sm" htmlFor="music-rotate">
              <input
                id="music-rotate"
                type="checkbox"
                checked={rotate}
                onChange={(event) => setRotate(event.target.checked)}
              />
              Rotate to the next song when one ends
            </label>
            <ul className="flex flex-col gap-4">
              {tracks.map((track, index) => (
                <li
                  key={`track-${index}`}
                  className="rounded-xl border border-muted/20 bg-bg/50 p-4"
                >
                  <p className="font-mono text-xs uppercase tracking-wider text-muted">
                    Track {index + 1}
                  </p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Field
                      id={`music-title-${index}`}
                      label="Title"
                      value={track.title}
                      onChange={(value) => updateTrack(index, { title: value })}
                    />
                    <Field
                      id={`music-url-${index}`}
                      label="URL or path"
                      value={track.url}
                      onChange={(value) => updateTrack(index, { url: value })}
                    />
                  </div>
                </li>
              ))}
            </ul>
            <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save music"}</SubmitButton>
          </form>
        </section>
      ) : null}

      {error ? <p className="text-sm text-error">{error}</p> : null}
      {notice ? <p className="text-sm text-success">{notice}</p> : null}
    </div>
  );
}
