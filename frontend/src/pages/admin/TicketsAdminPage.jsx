import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import {
  BUG_CATEGORIES,
  TICKET_STATUSES,
  categoryLabel,
  statusLabel,
} from "../../support/categories.js";

function formatWhen(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

export default function TicketsAdminPage() {
  const [search, setSearch] = useSearchParams();
  const selectedId = search.get("id") || "";
  const [statusFilter, setStatusFilter] = useState("");
  const [tickets, setTickets] = useState([]);
  const [detail, setDetail] = useState(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);

  const loadList = useCallback(async () => {
    const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
    const rows = await api(`/api/admin/tickets${query}`);
    setTickets(rows);
    return rows;
  }, [statusFilter]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        await loadList();
        if (!cancelled) setLoading(false);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load tickets.");
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [loadList]);

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

  async function changeStatus(next) {
    if (!detail || pending) return;
    setPending(true);
    setError("");
    try {
      const row = await api(`/api/admin/tickets/${detail.id}/status`, {
        method: "PATCH",
        body: { status: next },
      });
      setDetail(row);
      await loadList();
    } catch (err) {
      setError(err.message || "Could not update status.");
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return <p className="text-base text-muted">Loading tickets…</p>;
  }

  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">Studio</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Support tickets</h1>
          <p className="mt-2 text-base text-muted">
            Bug reports from learners and admins. Reply here — they see it under Messages.
          </p>
        </div>
        <label className="text-sm">
          Status
          <select
            className="ml-2 min-h-11 rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_28%,transparent)] bg-bg px-3"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All</option>
            {TICKET_STATUSES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      {error ? (
        <p className="text-sm text-error" role="status">
          {error}
        </p>
      ) : null}

      {!tickets.length ? (
        <p className="rounded-2xl bg-surface p-6 text-base text-muted">No tickets yet.</p>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)]">
          <ul className="flex max-h-[70vh] flex-col gap-2 overflow-auto">
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
                    <p className="mt-1 text-sm font-medium">{ticket.subject}</p>
                    <p className="mt-1 text-xs text-muted">
                      {ticket.creator_name || "User"} · {statusLabel(ticket.status)}
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
                {detail.creator_name} ({detail.creator_email}) · {categoryLabel(detail.category)}
              </p>
              <p className="mt-1 font-mono text-xs text-muted">
                {detail.page_path || "/"} · {detail.viewport} · {detail.user_agent.slice(0, 80)}
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                {TICKET_STATUSES.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`min-h-11 rounded-xl border-2 px-3 text-sm ${
                      detail.status === item.id
                        ? "border-accent bg-accent/15"
                        : "border-[color-mix(in_srgb,var(--text)_25%,transparent)]"
                    }`}
                    disabled={pending}
                    onClick={() => changeStatus(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

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
                      {message.is_from_staff ? " · You" : " · Reporter"} ·{" "}
                      {formatWhen(message.created_at)}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-base">{message.body}</p>
                  </li>
                ))}
              </ul>

              <form className="mt-5 flex flex-col gap-3" onSubmit={sendReply}>
                <label className="text-sm font-medium">
                  Reply to user
                  <textarea
                    className="mt-2 min-h-28 w-full rounded-xl border-2 border-[color-mix(in_srgb,var(--text)_28%,transparent)] bg-bg px-3 py-3 text-base"
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                    maxLength={4000}
                    placeholder="Thanks for the report — here's what we found…"
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

              <details className="mt-5 text-sm text-muted">
                <summary className="cursor-pointer text-accent">Captured context</summary>
                <pre className="mt-2 overflow-auto rounded-xl bg-bg p-3 font-mono text-xs">
                  {detail.context_json || "(none)"}
                </pre>
                <p className="mt-2 font-mono text-xs">{detail.page_url}</p>
              </details>
            </article>
          ) : (
            <p className="text-base text-muted">Select a ticket to reply.</p>
          )}
        </div>
      )}

      <p className="text-xs text-muted">
        Categories: {BUG_CATEGORIES.map((item) => item.label).join(" · ")}
      </p>
    </section>
  );
}
