import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";
import StrengthMeter from "../../components/layout/StrengthMeter.jsx";
import { passwordIsAcceptable } from "../../utils/password.js";

const emptyCreate = {
  firstName: "",
  lastName: "",
  email: "",
  password: "",
  role: "learner",
  tracks: [],
};

function listsFrom(rows) {
  const selection = {};
  const roles = {};
  for (const row of rows) {
    selection[row.id] = row.track_slugs;
    roles[row.id] = row.role;
  }
  return { selection, roles };
}

export default function UsersPage() {
  const { user: actor } = useOutletContext();
  const [users, setUsers] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [selection, setSelection] = useState({});
  const [roles, setRoles] = useState({});
  const [passwords, setPasswords] = useState({});
  const [createForm, setCreateForm] = useState(emptyCreate);
  const [showCreate, setShowCreate] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadUsers() {
    const rows = await api("/api/admin/users");
    const lists = listsFrom(rows);
    setUsers(rows);
    setSelection(lists.selection);
    setRoles(lists.roles);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [trackRows, userRows] = await Promise.all([
          api("/api/learn/tracks"),
          api("/api/admin/users"),
        ]);
        if (!cancelled) {
          const lists = listsFrom(userRows);
          setTracks(trackRows);
          setUsers(userRows);
          setSelection(lists.selection);
          setRoles(lists.roles);
          setCreateForm((current) => ({
            ...current,
            tracks: trackRows.map((track) => track.slug),
          }));
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return users;
    }
    return users.filter((row) => {
      const hay = `${row.first_name} ${row.last_name} ${row.email} ${row.role} ${row.status}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [query, users]);

  function toggleTrack(userId, slug) {
    setSelection((current) => {
      const selected = new Set(current[userId] || []);
      if (selected.has(slug)) {
        selected.delete(slug);
      } else {
        selected.add(slug);
      }
      return { ...current, [userId]: [...selected] };
    });
  }

  async function run(action) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await loadUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(event) {
    event.preventDefault();
    await run(async () => {
      await api("/api/admin/users", {
        method: "POST",
        body: {
          first_name: createForm.firstName,
          last_name: createForm.lastName,
          email: createForm.email,
          password: createForm.password,
          role: createForm.role,
          track_slugs: createForm.tracks,
        },
      });
      setCreateForm({
        ...emptyCreate,
        tracks: tracks.map((track) => track.slug),
      });
      setShowCreate(false);
      setNotice("User created.");
    });
  }

  const createReady =
    createForm.firstName.trim() &&
    createForm.lastName.trim() &&
    createForm.email.trim() &&
    passwordIsAcceptable(createForm.password);

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="mt-2 text-sm text-muted">
            Create accounts, assign tracks, and remove access. Only the super admin manages users.
          </p>
        </div>
        <button
          type="button"
          className="rounded-xl border border-muted/30 px-4 py-2 text-sm text-muted"
          onClick={() => setShowCreate((current) => !current)}
        >
          {showCreate ? "Close" : "Create user"}
        </button>
      </div>

      {showCreate ? (
        <form
          className="mt-6 flex flex-col gap-4 border-t border-muted/20 pt-6"
          onSubmit={onCreate}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              id="create-first-name"
              label="First name"
              value={createForm.firstName}
              onChange={(value) => setCreateForm((current) => ({ ...current, firstName: value }))}
              autoComplete="off"
            />
            <Field
              id="create-last-name"
              label="Last name"
              value={createForm.lastName}
              onChange={(value) => setCreateForm((current) => ({ ...current, lastName: value }))}
              autoComplete="off"
            />
          </div>
          <Field
            id="create-email"
            label="Email"
            type="email"
            value={createForm.email}
            onChange={(value) => setCreateForm((current) => ({ ...current, email: value }))}
            autoComplete="off"
          />
          <Field
            id="create-password"
            label="Password"
            type="password"
            value={createForm.password}
            onChange={(value) => setCreateForm((current) => ({ ...current, password: value }))}
            autoComplete="new-password"
          />
          <StrengthMeter password={createForm.password} />
          <label className="block text-sm text-muted" htmlFor="create-role">
            Role
            <select
              id="create-role"
              value={createForm.role}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, role: event.target.value }))
              }
              className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
            >
              <option value="learner">Learner</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <TrackChecks
            tracks={tracks}
            selected={createForm.tracks}
            onToggle={(slug) =>
              setCreateForm((current) => {
                const selected = new Set(current.tracks);
                if (selected.has(slug)) {
                  selected.delete(slug);
                } else {
                  selected.add(slug);
                }
                return { ...current, tracks: [...selected] };
              })
            }
          />
          <SubmitButton disabled={!createReady || busy}>Create user</SubmitButton>
        </form>
      ) : null}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-sm text-muted" htmlFor="users-search">
          Search
          <input
            id="users-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name or email"
            className="mt-1 block min-w-56 rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
          />
        </label>
        <p className="pb-2 text-sm text-muted">
          {visible.length} of {users.length} {users.length === 1 ? "account" : "accounts"}
        </p>
      </div>

      {notice ? <p className="mt-4 text-sm text-success">{notice}</p> : null}
      {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}

      <ul className="mt-6 flex flex-col gap-4">
        {visible.length === 0 ? <li className="text-sm text-muted">No accounts match.</li> : null}
        {visible.map((row) => {
          const mine = row.id === actor?.id;
          const active = row.status === "approved";
          return (
            <li key={row.id} className="rounded-xl border border-muted/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {row.first_name} {row.last_name}
                  </p>
                  <p className="mt-1 break-all text-sm text-muted">
                    {row.email} · {row.role}
                    {active ? "" : ` · ${row.status}`}
                  </p>
                </div>
                {!active ? (
                  <span className="rounded-full border border-muted/30 px-2.5 py-0.5 text-xs uppercase tracking-[0.12em] text-muted">
                    {row.status}
                  </span>
                ) : null}
              </div>
              <TrackChecks
                tracks={tracks}
                selected={selection[row.id] || []}
                onToggle={(slug) => toggleTrack(row.id, slug)}
              />
              <div className="mt-4 flex flex-wrap gap-2">
                <Action
                  disabled={busy}
                  onClick={() =>
                    run(() =>
                      api(`/api/admin/users/${row.id}/tracks`, {
                        method: "PUT",
                        body: { track_slugs: selection[row.id] || [] },
                      }),
                    )
                  }
                >
                  Save tracks
                </Action>
                {active ? (
                  <Action
                    disabled={busy || mine}
                    onClick={() =>
                      run(() =>
                        api(`/api/admin/users/${row.id}`, {
                          method: "PATCH",
                          body: { status: "disabled" },
                        }),
                      )
                    }
                  >
                    Disable
                  </Action>
                ) : (
                  <Action
                    disabled={busy || mine}
                    onClick={() =>
                      run(() =>
                        api(`/api/admin/users/${row.id}`, {
                          method: "PATCH",
                          body: { status: "approved" },
                        }),
                      )
                    }
                  >
                    Enable
                  </Action>
                )}
                <Action
                  disabled={busy}
                  onClick={() =>
                    run(() => api(`/api/admin/users/${row.id}/revoke-sessions`, { method: "POST" }))
                  }
                >
                  Revoke sessions
                </Action>
                <Action
                  disabled={busy || mine || row.role === "super_admin"}
                  onClick={() => {
                    if (
                      !window.confirm(
                        `Delete ${row.first_name} ${row.last_name}? This cannot be undone.`,
                      )
                    ) {
                      return;
                    }
                    run(async () => {
                      await api(`/api/admin/users/${row.id}`, { method: "DELETE" });
                      setNotice("User deleted.");
                    });
                  }}
                >
                  Delete
                </Action>
              </div>
              {row.role !== "super_admin" ? (
                <div className="mt-4 flex flex-wrap items-end gap-2">
                  <label className="text-sm text-muted" htmlFor={`role-${row.id}`}>
                    Role
                    <select
                      id={`role-${row.id}`}
                      value={roles[row.id] || row.role}
                      disabled={mine}
                      onChange={(event) =>
                        setRoles((current) => ({ ...current, [row.id]: event.target.value }))
                      }
                      className="mt-1 block rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
                    >
                      <option value="learner">Learner</option>
                      <option value="admin">Admin</option>
                    </select>
                  </label>
                  <Action
                    disabled={busy || mine}
                    onClick={() =>
                      run(() =>
                        api(`/api/admin/users/${row.id}`, {
                          method: "PATCH",
                          body: { role: roles[row.id] || row.role },
                        }),
                      )
                    }
                  >
                    Save role
                  </Action>
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted">Super admin role is fixed for this account.</p>
              )}
              <form
                className="mt-4 flex flex-wrap items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  run(async () => {
                    await api(`/api/admin/users/${row.id}/reset-password`, {
                      method: "POST",
                      body: { password: passwords[row.id] || "" },
                    });
                    setPasswords((current) => ({ ...current, [row.id]: "" }));
                    setNotice("Password reset. Their sessions were signed out.");
                  });
                }}
              >
                <div className="min-w-0 w-full flex-1 sm:min-w-52">
                  <Field
                    id={`reset-${row.id}`}
                    label="New password"
                    type="password"
                    value={passwords[row.id] || ""}
                    onChange={(value) =>
                      setPasswords((current) => ({ ...current, [row.id]: value }))
                    }
                    autoComplete="new-password"
                  />
                </div>
                <SubmitButton disabled={busy || !passwordIsAcceptable(passwords[row.id] || "")}>
                  Reset password
                </SubmitButton>
              </form>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function TrackChecks({ tracks, selected, onToggle }) {
  return (
    <fieldset className="mt-3">
      <legend className="text-sm text-muted">Tracks</legend>
      <div className="mt-2 flex flex-wrap gap-3">
        {tracks.map((track) => (
          <label key={track.slug} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.includes(track.slug)}
              onChange={() => onToggle(track.slug)}
            />
            {track.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Action({ children, disabled, onClick }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-xl border border-muted/30 px-3 py-2 text-sm text-muted disabled:opacity-50"
    >
      {children}
    </button>
  );
}
