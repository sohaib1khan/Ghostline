import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { SubmitButton } from "../../components/layout/Field.jsx";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "ollama", label: "Ollama" },
];

export default function AiPage() {
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [maxTokens, setMaxTokens] = useState(4096);
  const [timeoutSeconds, setTimeoutSeconds] = useState(45);
  const [enabled, setEnabled] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [keySet, setKeySet] = useState(false);
  const [clearKey, setClearKey] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api("/api/admin/ai/settings")
      .then((data) => {
        if (cancelled) {
          return;
        }
        setProvider(data.provider);
        setModel(data.model || "");
        setBaseUrl(data.base_url || "");
        setMaxTokens(data.max_tokens);
        setTimeoutSeconds(data.timeout_seconds);
        setEnabled(data.enabled);
        setKeySet(data.api_key_set);
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
      const data = await api("/api/admin/ai/settings", {
        method: "PUT",
        body: {
          provider,
          model,
          base_url: baseUrl,
          max_tokens: Number(maxTokens),
          timeout_seconds: Number(timeoutSeconds),
          enabled,
          api_key: apiKey,
          clear_api_key: clearKey,
        },
      });
      setProvider(data.provider);
      setModel(data.model || "");
      setBaseUrl(data.base_url || "");
      setMaxTokens(data.max_tokens);
      setTimeoutSeconds(data.timeout_seconds);
      setEnabled(data.enabled);
      setKeySet(data.api_key_set);
      setApiKey("");
      setClearKey(false);
      setNotice("AI settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    setNotice("");
    setError("");
    try {
      const data = await api("/api/admin/ai/test", { method: "POST" });
      setNotice(data.detail || "Connected.");
    } catch (err) {
      setError(err.message);
    } finally {
      setTesting(false);
    }
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">AI</h1>
      <p className="mt-2 max-w-xl text-sm text-muted">
        Drafts stay unpublished until you review them. The API key is encrypted and is not shown
        again after you save it.
      </p>
      <form className="mt-6 flex max-w-md flex-col gap-6" onSubmit={save}>
        <fieldset className="flex flex-col gap-4 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Connection</legend>
          <label className="text-sm">
            Provider
            <select
              className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              aria-label="Provider"
            >
              {PROVIDERS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Model
            <input
              className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              required
              aria-label="Model"
            />
          </label>
          {provider === "ollama" ? (
            <label className="text-sm">
              Base URL
              <input
                className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="http://127.0.0.1:11434"
                aria-label="Base URL"
              />
            </label>
          ) : null}
          <label className="text-sm">
            API key
            <input
              className="mt-1 w-full rounded-xl border border-muted/30 bg-bg px-3 py-2"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
              placeholder={keySet ? "••••••" : ""}
              aria-label="API key"
            />
          </label>
          <p className="text-sm text-muted">
            {keySet
              ? "A key is saved. Leave the field blank to keep it, or type a new one to replace it."
              : "Anthropic and OpenAI need a key. Ollama uses one only if you set it."}
          </p>
          {keySet ? (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={clearKey}
                onChange={(event) => setClearKey(event.target.checked)}
              />
              Remove the saved key
            </label>
          ) : null}
        </fieldset>
        <fieldset className="flex flex-col gap-4 border-t border-muted/20 pt-4">
          <legend className="text-sm font-medium text-text">Limits</legend>
          <div className="flex gap-3">
            <label className="text-sm">
              Max tokens
              <input
                className="mt-1 w-28 rounded-xl border border-muted/30 bg-bg px-3 py-2"
                type="number"
                min="256"
                max="8192"
                value={maxTokens}
                onChange={(event) => setMaxTokens(event.target.value)}
                aria-label="Max tokens"
              />
            </label>
            <label className="text-sm">
              Timeout (seconds)
              <input
                className="mt-1 w-28 rounded-xl border border-muted/30 bg-bg px-3 py-2"
                type="number"
                min="5"
                max="120"
                value={timeoutSeconds}
                onChange={(event) => setTimeoutSeconds(event.target.value)}
                aria-label="Timeout in seconds"
              />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            Enable AI drafts
          </label>
        </fieldset>
        {error ? <p className="text-sm text-error">{error}</p> : null}
        {notice ? <p className="text-sm text-success">{notice}</p> : null}
        <div className="flex flex-wrap gap-2">
          <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save AI settings"}</SubmitButton>
          <button
            type="button"
            className="rounded-xl border border-muted/30 px-4 py-2 text-sm disabled:opacity-50"
            onClick={testConnection}
            disabled={testing}
          >
            {testing ? "Testing…" : "Test connection"}
          </button>
        </div>
        <p className="text-sm text-muted">
          Test connection uses the settings that are already saved.
        </p>
      </form>
    </section>
  );
}
