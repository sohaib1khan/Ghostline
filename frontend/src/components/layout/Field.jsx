export function Field({ id, label, type = "text", value, onChange, autoComplete, hint }) {
  return (
    <label className="block" htmlFor={id}>
      <span className="mb-1 block text-sm text-muted">{label}</span>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-muted/30 bg-bg px-3 py-2 text-text outline-none focus:border-accent"
      />
      {hint ? <span className="mt-1 block text-sm text-muted">{hint}</span> : null}
    </label>
  );
}

export function SubmitButton({ children, disabled }) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="rounded-xl bg-accent px-4 py-2 font-medium text-[#1b1f23] disabled:opacity-50"
    >
      {children}
    </button>
  );
}
