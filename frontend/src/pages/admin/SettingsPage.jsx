import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { SubmitButton } from "../../components/layout/Field.jsx";

export default function SettingsPage() {
  const [enabled, setEnabled] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api("/api/admin/settings")
      .then((data) => {
        if (!cancelled) {
          setEnabled(data.leaderboard_enabled);
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

  async function save(event) {
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
      setNotice("Settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Leaderboard</h1>
      <p className="mt-2 text-sm text-muted">Site-wide visibility for learner XP.</p>
      <form className="mt-6 flex max-w-md flex-col gap-5" onSubmit={save}>
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
          When this is on, learners see first names and XP on the stats page. It stays off until you
          turn it on.
        </p>
        {error ? <p className="text-sm text-error">{error}</p> : null}
        {notice ? <p className="text-sm text-success">{notice}</p> : null}
        <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save settings"}</SubmitButton>
      </form>
    </section>
  );
}
