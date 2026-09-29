import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client.js";
import { Field, SubmitButton } from "../../components/layout/Field.jsx";
import StrengthMeter from "../../components/layout/StrengthMeter.jsx";
import { passwordIsAcceptable } from "../../utils/password.js";

export default function ProfilePage() {
  const { user, setUser } = useOutletContext();
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  if (!user) {
    return null;
  }

  async function saveName(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setPending(true);
    try {
      const updated = await api("/api/me", {
        method: "PATCH",
        body: { first_name: firstName, last_name: lastName },
      });
      setUser(updated);
      setNotice("Name saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setPending(true);
    try {
      await api("/api/me/password", {
        method: "POST",
        body: { current_password: currentPassword, new_password: newPassword },
      });
      setCurrentPassword("");
      setNewPassword("");
      setNotice("Password changed. Other sessions were signed out.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="mt-2 text-sm text-muted">{user.email}</p>
        <form className="mt-6 flex flex-col gap-4" onSubmit={saveName}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              id="profile-first-name"
              label="First name"
              value={firstName}
              onChange={setFirstName}
              autoComplete="given-name"
            />
            <Field
              id="profile-last-name"
              label="Last name"
              value={lastName}
              onChange={setLastName}
              autoComplete="family-name"
            />
          </div>
          <SubmitButton disabled={pending || !firstName.trim() || !lastName.trim()}>
            Save name
          </SubmitButton>
        </form>
      </section>
      <section className="rounded-2xl bg-surface p-6 shadow-[var(--shadow)]">
        <h2 className="text-lg font-semibold tracking-tight">Password</h2>
        <form className="mt-4 flex flex-col gap-4" onSubmit={savePassword}>
          <Field
            id="current-password"
            label="Current password"
            type="password"
            value={currentPassword}
            onChange={setCurrentPassword}
            autoComplete="current-password"
          />
          <Field
            id="new-password"
            label="New password"
            type="password"
            value={newPassword}
            onChange={setNewPassword}
            autoComplete="new-password"
          />
          <StrengthMeter password={newPassword} />
          <SubmitButton
            disabled={pending || !currentPassword || !passwordIsAcceptable(newPassword)}
          >
            Change password
          </SubmitButton>
        </form>
      </section>
      {notice ? <p className="text-sm text-success">{notice}</p> : null}
      {error ? <p className="text-sm text-error">{error}</p> : null}
    </div>
  );
}
