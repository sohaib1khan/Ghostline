import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";

const EMPTY = {
  enabled: true,
  title: "Certificate of Completion",
  subtitle: "This certifies that",
  body: "has successfully completed the {track} learning path.",
  signer_name: "Ghostline",
  signer_title: "Typing-first practice",
  footer: "Keep typing. Keep the muscle memory.",
};

export default function CertificateSettingsPage() {
  const [form, setForm] = useState(EMPTY);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api("/api/admin/certificates")
      .then((data) => {
        if (!cancelled) {
          setForm({ ...EMPTY, ...data });
          setLoaded(true);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoaded(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function patch(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(event) {
    event.preventDefault();
    setPending(true);
    setNotice("");
    setError("");
    try {
      const data = await api("/api/admin/certificates", {
        method: "PUT",
        body: form,
      });
      setForm({ ...EMPTY, ...data });
      setNotice("Certificate settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  if (!loaded && !error) {
    return <p className="text-sm text-muted">Loading…</p>;
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Certificates</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Super admin only. Learners always see a watermarked preview with their profile name. The
        full certificate (with ID, print/save) unlocks when a track is complete. Use{" "}
        <code className="font-mono text-xs text-text">{"{track}"}</code> in the body for the course
        name.
      </p>
      <form className="mt-6 flex max-w-xl flex-col gap-4" onSubmit={save}>
        <label className="flex items-center gap-2 text-sm" htmlFor="cert-enabled">
          <input
            id="cert-enabled"
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => patch("enabled", event.target.checked)}
          />
          Enable certificates
        </label>
        <Field
          id="cert-title"
          label="Title"
          value={form.title}
          onChange={(value) => patch("title", value)}
        />
        <Field
          id="cert-subtitle"
          label="Subtitle"
          value={form.subtitle}
          onChange={(value) => patch("subtitle", value)}
        />
        <label className="block text-sm text-muted" htmlFor="cert-body">
          Body
          <textarea
            id="cert-body"
            value={form.body}
            onChange={(event) => patch("body", event.target.value)}
            rows={3}
            className="mt-1 block w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text"
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="cert-signer"
            label="Signer name"
            value={form.signer_name}
            onChange={(value) => patch("signer_name", value)}
          />
          <Field
            id="cert-signer-title"
            label="Signer title"
            value={form.signer_title}
            onChange={(value) => patch("signer_title", value)}
          />
        </div>
        <Field
          id="cert-footer"
          label="Footer"
          value={form.footer}
          onChange={(value) => patch("footer", value)}
        />
        {error ? <p className="text-sm text-error">{error}</p> : null}
        {notice ? <p className="text-sm text-success">{notice}</p> : null}
        <SubmitButton disabled={pending}>{pending ? "Saving…" : "Save certificates"}</SubmitButton>
      </form>
    </section>
  );
}
