import { useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";

export default function LoginPage() {
  const navigate = useNavigate();
  const { setUser } = useOutletContext();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const user = await api("/api/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setUser(user);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-2 text-sm text-muted">
        Pick up the streak. The lines you practiced are waiting.
      </p>
      <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
        <Field
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="username"
        />
        <Field
          id="password"
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />
        {error ? <p className="text-sm text-error">{error}</p> : null}
        <SubmitButton disabled={!email || !password || pending}>
          {pending ? "Signing in…" : "Sign in"}
        </SubmitButton>
      </form>
      <Link to="/signup" className="mt-4 inline-block text-sm text-accent">
        Need an account? Request access
      </Link>
    </section>
  );
}
