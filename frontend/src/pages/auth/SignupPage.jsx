import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";
import StrengthMeter from "../../components/layout/StrengthMeter.jsx";
import { passwordIsAcceptable } from "../../utils/password.js";

export default function SignupPage() {
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
  });
  const [message, setMessage] = useState("");
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
      const result = await api("/api/auth/signup", {
        method: "POST",
        body: {
          first_name: form.firstName,
          last_name: form.lastName,
          email: form.email,
          password: form.password,
        },
      });
      setMessage(result.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  if (message) {
    return (
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold tracking-tight">You are in</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">{message}</p>
        <Link to="/login" className="mt-6 inline-block text-sm text-accent">
          Sign in
        </Link>
      </section>
    );
  }

  const ready =
    form.firstName.trim() &&
    form.lastName.trim() &&
    form.email.trim() &&
    passwordIsAcceptable(form.password);

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Create an account</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Sign up and start practicing right away. Tracks are ready when you sign in.
      </p>
      <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="signup-first-name"
            label="First name"
            value={form.firstName}
            onChange={update("firstName")}
            autoComplete="given-name"
          />
          <Field
            id="signup-last-name"
            label="Last name"
            value={form.lastName}
            onChange={update("lastName")}
            autoComplete="family-name"
          />
        </div>
        <Field
          id="signup-email"
          label="Email"
          type="email"
          value={form.email}
          onChange={update("email")}
          autoComplete="email"
        />
        <Field
          id="signup-password"
          label="Password"
          type="password"
          value={form.password}
          onChange={update("password")}
          autoComplete="new-password"
        />
        <StrengthMeter password={form.password} />
        {error ? <p className="text-sm text-error">{error}</p> : null}
        <SubmitButton disabled={!ready || pending}>
          {pending ? "Creating…" : "Create account"}
        </SubmitButton>
      </form>
      <Link to="/login" className="mt-4 inline-block text-sm text-accent">
        Already have an account? Sign in
      </Link>
    </section>
  );
}
