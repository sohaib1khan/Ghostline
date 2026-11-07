import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { categoryLabel, statusLabel } from "../../support/categories.js";

function formatWhen(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

export default function MessagesPage() {
  const [search, setSearch] = useSearchParams();
  const selectedId = search.get("id") || "";
  const [tickets, setTickets] = useState([]);
  const [detail, setDetail] = useState(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);

  const loadList = useCallback(async () => {
    const rows = await api("/api/tickets");
    setTickets(rows);
    return rows;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const rows = await loadList();
        if (cancelled) return;
        setLoading(false);
        if (!selectedId && rows[0]) {
          setSearch({ id: rows[0].id }, { replace: true });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load messages.");
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [loadList, selectedId, setSearch]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return undefined;
    }
    let cancelled = false;
    async function load() {
      try {
        const row = await api(`/api/tickets/${selectedId}`);
        if (!cancelled) {
          setDetail(row);
          setError("");
          setTickets((current) =>
            current.map((item) => (item.id === row.id ? { ...item, unread: false } : item)),
          );
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Could not open ticket.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function sendReply(event) {
    event.preventDefault();
    if (!detail || pending) return;
    const text = reply.trim();
    if (!text) return;
    setPending(true);
    setError("");
    try {
      const row = await api(`/api/tickets/${detail.id}/reply`, {
        method: "POST",
        body: { body: text },
      });
      setDetail(row);
      setReply("");
      await loadList();
    } catch (err) {
      setError(err.message || "Reply failed.");
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return <p className="text-base text-muted">Loading messages…</p>;
  }

  return (
    <section className="flex flex-col gap-5">
      <header>
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">Support</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Messages</h1>
        <p className="mt-2 text-base text-muted">
          Bug reports you sent and replies from the Ghostline team.
        </p>
      </header>

      {error ? (
        <p className="text-sm text-error" role="status">
          {error}
        </p>
      ) : null}

      {!tickets.length ? (
        <div className="rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_20%,transparent)] bg-surface p-6">
          <p className="text-base text-muted">No messages yet.</p>
          <p className="mt-2 text-sm text-muted">
            Use <strong className="text-text">Report bug</strong> anywhere in the app if something
            breaks.
          </p>
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(14rem,20rem)_minmax(0,1fr)]">
          <ul className="flex flex-col gap-2">
            {tickets.map((ticket) => {
              const active = ticket.id === selectedId;
              return (
                <li key={ticket.id}>
                  <button
                    type="button"
                    className={`w-full rounded-2xl border-2 px-4 py-3 text-left ${
                      active
                        ? "border-accent bg-accent/10"
                        : "border-[color-mix(in_srgb,var(--text)_18%,transparent)] bg-surface"
                    }`}
                    onClick={() => setSearch({ id: ticket.id })}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-accent">{ticket.public_id}</span>
                      {ticket.unread ? (
                        <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-on-accent">
                          New
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm font-medium text-text">{ticket.subject}</p>
                    <p className="mt-1 text-xs text-muted">
                      {statusLabel(ticket.status)} · {formatWhen(ticket.last_message_at)}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>

          {detail ? (
            <article className="rounded-2xl border-2 border-[color-mix(in_srgb,var(--text)_20%,transparent)] bg-surface p-4 sm:p-6">
              <p className="font-mono text-sm text-accent">{detail.public_id}</p>
              <h2 className="mt-1 text-2xl font-semibold">{detail.subject}</h2>
              <p className="mt-2 text-sm text-muted">
                {categoryLabel(detail.category)} · {statusLabel(detail.status)} ·{" "}
                <span className="font-mono">{detail.page_path || "/"}</span>
              </p>

              <ul className="mt-5 flex flex-col gap-3">
                {detail.messages.map((message) => (
                  <li
                    key={message.id}
                    className={`rounded-xl border px-4 py-3 ${
                      message.is_from_staff
                        ? "border-accent/40 bg-accent/10"
                        : "border-[color-mix(in_srgb,var(--text)_16%,transparent)] bg-bg"
                    }`}
                  >
                    <p className="text-xs text-muted">
                      {message.author_name}
                      {message.is_from_staff ? " · Support" : ""} · {formatWhen(message.created_at)}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-base text-text">{message.body}</p>
                  </li>
                ))}
              </ul>

              {detail.status !== "closed" ? (
                <form className="mt-5 flex flex-col gap-3" onSubmit={sendReply}>
                  <label className="text-sm font-medium">
                    Reply
                    <textarea
                      className="mt-2 min-h-24 w-full rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_28%,transparent)] bg-bg px-3 py-3 text-base"
                      value={reply}
                      onChange={(event) => setReply(event.target.value)}
                      maxLength={4000}
                      placeholder="Add more detail or ask a follow-up…"
                    />
                  </label>
                  <button
                    type="submit"
                    className="min-h-12 w-fit rounded-xl bg-accent px-5 text-base font-semibold text-on-accent disabled:opacity-50"
                    disabled={pending || !reply.trim()}
                  >
                    {pending ? "Sending…" : "Send reply"}
                  </button>
                </form>
              ) : (
                <p className="mt-5 text-sm text-muted">This ticket is closed.</p>
              )}
            </article>
          ) : (
            <p className="text-base text-muted">Pick a message on the left.</p>
          )}
        </div>
      )}

      <Link to="/" className="text-base text-accent underline">
        Back home
      </Link>
    </section>
  );
}
