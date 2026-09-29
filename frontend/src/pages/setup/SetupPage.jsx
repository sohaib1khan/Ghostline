import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";
import StrengthMeter from "../../components/layout/StrengthMeter.jsx";
import { passwordIsAcceptable } from "../../utils/password.js";

export default function SetupPage() {
  const navigate = useNavigate();
  const { setSetupRequired } = useOutletContext();
  const [form, setForm] = useState({
    setupToken: "",
    firstName: "",
    lastName: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  function update(key) {
    return (value) => setForm((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      await api("/api/setup", {
        method: "POST",
        body: {
          setup_token: form.setupToken.trim(),
          first_name: form.firstName,
          last_name: form.lastName,
          email: form.email,
          password: form.password,
        },
      });
      setSetupRequired(false);
      navigate("/login");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  const ready =
    form.setupToken.trim().length >= 20 &&
    form.firstName.trim() &&
    form.lastName.trim() &&
    form.email.trim() &&
    passwordIsAcceptable(form.password);

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Create the admin account</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        The one-time setup token is printed in the backend logs. After this account exists, setup
        closes.
      </p>
      <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
        <Field
          id="setup-token"
          label="Setup token"
          value={form.setupToken}
          onChange={update("setupToken")}
          autoComplete="off"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="first-name"
            label="First name"
            value={form.firstName}
            onChange={update("firstName")}
            autoComplete="given-name"
          />
          <Field
            id="last-name"
            label="Last name"
            value={form.lastName}
            onChange={update("lastName")}
            autoComplete="family-name"
          />
        </div>
        <Field
          id="email"
          label="Email"
          type="email"
          value={form.email}
          onChange={update("email")}
          autoComplete="email"
        />
        <Field
          id="password"
          label="Password"
          type="password"
          value={form.password}
          onChange={update("password")}
          autoComplete="new-password"
        />
        <StrengthMeter password={form.password} />
        {error ? <p className="text-sm text-error">{error}</p> : null}
        <SubmitButton disabled={!ready || pending}>
          {pending ? "Creating…" : "Create admin"}
        </SubmitButton>
      </form>
    </section>
  );
}
