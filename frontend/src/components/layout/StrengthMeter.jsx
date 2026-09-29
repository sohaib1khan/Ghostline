import { passwordStrength } from "../../utils/password.js";

export default function StrengthMeter({ password }) {
  const strength = passwordStrength(password);
  const width = ["w-0", "w-1/3", "w-2/3", "w-full"][strength.score];
  return (
    <div>
      <div className="strength-track h-1.5 overflow-hidden rounded-full" aria-hidden="true">
        <div className={`h-full rounded-full strength-${strength.score} ${width}`} />
      </div>
      <p className="mt-1 text-sm text-muted" aria-live="polite">
        {strength.label}
      </p>
    </div>
  );
}
