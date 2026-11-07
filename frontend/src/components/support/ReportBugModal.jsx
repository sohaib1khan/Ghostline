import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { BUG_CATEGORIES, captureBugContext } from "../../support/categories.js";

export default function ReportBugModal({ open, onClose, onSubmitted }) {
  const titleId = useId();
  const firstField = useRef(null);
  const [category, setCategory] = useState("page_broken");
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const [context] = useState(() => captureBugContext());

  useEffect(() => {
    if (!open) return undefined;
    setCategory("page_broken");
    setBody("");
    setError("");
    setDone(null);
    setPending(false);
    const timer = window.setTimeout(() => firstField.current?.focus(), 40);
    function onKey(event) {
      if (event.key === "Escape" && !pending) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose, pending]);

  if (!open) return null;

  async function submit(event) {
    event.preventDefault();
    if (pending) return;
    const text = body.trim();
    if (!text) {
      setError("Tell us what went wrong in a sentence or two.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const snap = captureBugContext();
      const ticket = await api("/api/tickets", {
        method: "POST",
        body: {
          category,
          body: text,
          page_url: snap.page_url,
          page_path: snap.page_path,
          user_agent: snap.user_agent,
          viewport: snap.viewport,
          context_json: snap.context_json,
        },
      });
      setDone(ticket);
      if (onSubmitted) onSubmitted(ticket);
    } catch (err) {
      setError(err.message || "Could not send the report.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      className="report-bug-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !pending) onClose();
      }}
    >
      <div
        className="report-bug-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        {done ? (
          <div className="flex flex-col gap-4 p-5 sm:p-6">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">Report sent</p>
            <h2 id={titleId} className="text-2xl font-semibold tracking-tight">
              Thanks — we got it
            </h2>
            <p className="text-base text-muted">
              Your ticket id is{" "}
              <span className="font-mono font-semibold text-text">{done.public_id}</span>. Replies
              show up under Messages.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/messages"
                className="inline-flex min-h-12 items-center rounded-xl bg-accent px-4 text-base font-semibold text-on-accent"
                onClick={onClose}
              >
                Open Messages
              </Link>
              <button
                type="button"
                className="min-h-12 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_30%,transparent)] px-4 text-base"
                onClick={onClose}
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <form className="flex flex-col gap-4 p-5 sm:p-6" onSubmit={submit}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">
                  Report a bug
                </p>
                <h2 id={titleId} className="mt-1 text-2xl font-semibold tracking-tight">
                  What went wrong?
                </h2>
              </div>
              <button
                type="button"
                className="min-h-11 rounded-xl px-3 text-sm text-muted"
                onClick={onClose}
                disabled={pending}
              >
                Close
              </button>
            </div>

            <p className="text-sm text-muted">
              We already captured this page (
              <span className="font-mono text-text">{context.page_path || "/"}</span>
              ). Pick a type, add a short note, and send.
            </p>

            <fieldset>
              <legend className="text-sm font-medium text-text">Likely issue</legend>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {BUG_CATEGORIES.map((item) => (
                  <label
                    key={item.id}
                    className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border-2 px-3 py-2 text-sm ${
                      category === item.id
                        ? "border-accent bg-accent/15 font-medium"
                        : "border-[color-mix(in_srgb,var(--text)_22%,transparent)]"
                    }`}
                  >
                    <input
                      ref={item.id === "page_broken" ? firstField : undefined}
                      type="radio"
                      name="bug-category"
                      value={item.id}
                      checked={category === item.id}
                      onChange={() => setCategory(item.id)}
                      className="accent-[var(--accent)]"
                    />
                    {item.label}
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="block text-sm font-medium text-text">
              What happened?
              <textarea
                className="mt-2 min-h-28 w-full rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_28%,transparent)] bg-bg px-3 py-3 text-base text-text"
                value={body}
                onChange={(event) => setBody(event.target.value)}
                maxLength={4000}
                placeholder="Example: I clicked Check on the Bash lesson and nothing happened."
                required
              />
            </label>

            {error ? (
              <p className="text-sm text-error" role="status">
                {error}
              </p>
            ) : null}

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                className="min-h-12 rounded-xl bg-accent px-5 text-base font-semibold text-on-accent disabled:opacity-50"
                disabled={pending}
              >
                {pending ? "Sending…" : "Send report"}
              </button>
              <button
                type="button"
                className="min-h-12 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_30%,transparent)] px-4 text-base"
                onClick={onClose}
                disabled={pending}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
