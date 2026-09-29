import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";

const EVENTS = [
  ["user.signup", "New signup"],
  ["user.approved", "Access approved"],
  ["user.rejected", "Access rejected"],
  ["admin.login", "Admin sign-in"],
  ["content.published", "Lesson published"],
];

const PROVIDERS = [
  ["resend", "Resend"],
  ["smtp", "SMTP"],
  ["gotify", "Gotify"],
  ["slack", "Slack"],
  ["discord", "Discord"],
  ["ntfy", "ntfy"],
  ["webhook", "Webhook"],
];

const FIELDS = {
  resend: [
    ["api_key", "API key", "password", true],
    ["from_email", "From address", "email", false],
    ["to_email", "Admin address", "email", false],
  ],
  smtp: [
    ["host", "Host", "text", false],
    ["port", "Port", "text", false],
    ["username", "Username", "text", false],
    ["password", "Password", "password", true],
    ["from_email", "From address", "email", false],
    ["to_email", "Admin address", "email", false],
  ],
  gotify: [
    ["base_url", "Server URL", "url", false],
    ["token", "App token", "password", true],
    ["priority", "Priority (0–10)", "text", false],
  ],
  slack: [["webhook_url", "Webhook URL", "password", true]],
  discord: [["webhook_url", "Webhook URL", "password", true]],
  ntfy: [
    ["base_url", "Server URL", "url", false],
    ["topic", "Topic", "text", false],
    ["token", "Access token", "password", true],
  ],
  webhook: [
    ["url", "URL", "url", false],
    ["bearer_token", "Bearer token", "password", true],
  ],
};

function emptyConfig(provider) {
  const config = {};
  for (const [key] of FIELDS[provider]) {
    config[key] = "";
  }
  if (provider === "smtp") {
    config.port = "587";
    config.security = "starttls";
  }
  if (provider === "gotify") {
    config.priority = "5";
  }
  return config;
}

function blankForm() {
  return {
    id: null,
    name: "",
    provider: "webhook",
    events: ["user.signup"],
    isEnabled: true,
    config: emptyConfig("webhook"),
    savedSecrets: {},
  };
}

function testLabel(row) {
  if (row.last_test_ok === true) {
    return "Last test sent";
  }
  if (row.last_test_ok === false) {
    return "Last test failed";
  }
  return "Not tested yet";
}

export default function NotificationsPage() {
  const [channels, setChannels] = useState([]);
  const [emailReady, setEmailReady] = useState(true);
  const [form, setForm] = useState(blankForm);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api("/api/admin/notifications/channels");
        if (!cancelled) {
          setChannels(data.channels);
          setEmailReady(data.email_channel_ready);
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

  async function reload() {
    const data = await api("/api/admin/notifications/channels");
    setChannels(data.channels);
    setEmailReady(data.email_channel_ready);
  }

  function edit(row) {
    const config = emptyConfig(row.provider);
    for (const [key, value] of Object.entries(row.config || {})) {
      config[key] = value === null || value === undefined ? "" : String(value);
    }
    setForm({
      id: row.id,
      name: row.name,
      provider: row.provider,
      events: row.events,
      isEnabled: row.is_enabled,
      config,
      savedSecrets: row.secrets || {},
    });
    setShowForm(true);
    setNotice("");
    setError("");
  }

  function changeProvider(provider) {
    setForm((current) => ({
      ...current,
      provider,
      config: emptyConfig(provider),
      savedSecrets: {},
    }));
  }

  function toggleEvent(eventName) {
    setForm((current) => {
      const events = current.events.includes(eventName)
        ? current.events.filter((item) => item !== eventName)
        : [...current.events, eventName];
      return { ...current, events };
    });
  }

  async function onSave(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setNotice("");
    const config = { ...form.config };
    if (form.provider === "smtp") {
      config.port = Number(config.port);
    }
    if (form.provider === "gotify" && config.priority !== "") {
      config.priority = Number(config.priority);
    }
    const body = {
      name: form.name,
      provider: form.provider,
      events: form.events,
      is_enabled: form.isEnabled,
      config,
    };
    try {
      if (form.id) {
        await api(`/api/admin/notifications/channels/${form.id}`, { method: "PUT", body });
      } else {
        await api("/api/admin/notifications/channels", { method: "POST", body });
      }
      await reload();
      setForm(blankForm());
      setShowForm(false);
      setNotice("Channel saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function onDelete(row) {
    setPending(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/admin/notifications/channels/${row.id}`, { method: "DELETE" });
      if (form.id === row.id) {
        setForm(blankForm());
        setShowForm(false);
      }
      await reload();
      setNotice("Channel deleted.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function onTest(row) {
    setPending(true);
    setError("");
    setNotice("");
    try {
      const result = await api(`/api/admin/notifications/channels/${row.id}/test`, {
        method: "POST",
      });
      await reload();
      setNotice(result.detail);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  const fields = FIELDS[form.provider];

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Notifications</h1>
          <p className="mt-2 text-sm text-muted">
            Choose where signup, approval, and admin sign-in notices are sent.
          </p>
        </div>
        <button
          type="button"
          className="rounded-xl border border-muted/30 px-4 py-2 text-sm text-muted"
          onClick={() => {
            setShowForm((current) => !current);
            setForm(blankForm());
            setError("");
            setNotice("");
          }}
        >
          {showForm ? "Close" : "Add channel"}
        </button>
      </div>

      {emailReady ? null : (
        <p className="mt-4 rounded-xl border border-muted/30 px-4 py-3 text-sm text-muted">
          Approval and rejection emails need an enabled Resend or SMTP channel.
        </p>
      )}
      {error ? <p className="mt-4 text-sm text-error">{error}</p> : null}
      {notice ? <p className="mt-4 text-sm text-muted">{notice}</p> : null}

      {showForm ? (
        <form className="mt-6 flex flex-col gap-4 border-t border-muted/20 pt-6" onSubmit={onSave}>
          <Field
            id="channel-name"
            label="Name"
            value={form.name}
            onChange={(value) => setForm((current) => ({ ...current, name: value }))}
          />
          <label className="block" htmlFor="channel-provider">
            <span className="mb-1 block text-sm text-muted">Provider</span>
            <select
              id="channel-provider"
              value={form.provider}
              onChange={(event) => changeProvider(event.target.value)}
              className="w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text outline-none focus:border-accent"
            >
              {PROVIDERS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend className="mb-2 text-sm text-muted">Events</legend>
            <div className="flex flex-col gap-2">
              {EVENTS.map(([value, label]) => (
                <label key={value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.events.includes(value)}
                    onChange={() => toggleEvent(value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            <span className="mt-1 block text-sm text-muted">
              Lesson published starts sending when lessons can be published.
            </span>
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.isEnabled}
              onChange={(event) =>
                setForm((current) => ({ ...current, isEnabled: event.target.checked }))
              }
            />
            <span>Enabled</span>
          </label>
          {fields.map(([key, label, type, secret]) => (
            <Field
              key={key}
              id={`channel-${key}`}
              label={label}
              type={secret ? "password" : type}
              value={form.config[key] ?? ""}
              autoComplete="off"
              hint={
                secret && form.savedSecrets[key]
                  ? "Saved. Enter a new value to replace it."
                  : key === "to_email"
                    ? "Used for signup and admin sign-in. Approval mail goes to the learner."
                    : key === "url"
                      ? "Do not put secrets in the URL. Use the bearer token field."
                      : ""
              }
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  config: { ...current.config, [key]: value },
                }))
              }
            />
          ))}
          {form.provider === "smtp" ? (
            <label className="block" htmlFor="channel-security">
              <span className="mb-1 block text-sm text-muted">Security</span>
              <select
                id="channel-security"
                value={form.config.security || "starttls"}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    config: { ...current.config, security: event.target.value },
                  }))
                }
                className="w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text outline-none focus:border-accent"
              >
                <option value="starttls">STARTTLS</option>
                <option value="ssl">SSL</option>
                <option value="none">None</option>
              </select>
            </label>
          ) : null}
          <SubmitButton disabled={pending || !form.name.trim()}>
            {pending ? "Saving…" : "Save channel"}
          </SubmitButton>
        </form>
      ) : null}

      <ul className="mt-6 flex flex-col gap-3">
        {channels.length === 0 ? (
          <li className="text-sm text-muted">No channels yet.</li>
        ) : (
          channels.map((row) => (
            <li key={row.id} className="rounded-xl border border-muted/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{row.name}</p>
                  <p className="mt-1 text-sm text-muted">
                    {row.provider}
                    {row.is_enabled ? "" : " · disabled"}
                    {" · "}
                    {row.events.length ? row.events.join(", ") : "no events"}
                  </p>
                  <p className="mt-1 text-sm text-muted">{testLabel(row)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded-xl border border-muted/30 px-3 py-2 text-sm text-muted disabled:opacity-50"
                    disabled={pending}
                    onClick={() => onTest(row)}
                  >
                    Send test
                  </button>
                  <button
                    type="button"
                    className="rounded-xl border border-muted/30 px-3 py-2 text-sm text-muted disabled:opacity-50"
                    disabled={pending}
                    onClick={() => edit(row)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="rounded-xl border border-muted/30 px-3 py-2 text-sm text-muted disabled:opacity-50"
                    disabled={pending}
                    onClick={() => onDelete(row)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </li>
          ))
        )}
      </ul>
    </section>
  );
}
