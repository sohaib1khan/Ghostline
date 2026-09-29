import { wordsOf } from "./fill.js";

export default function FillGap({ code, blanks, values, onChange, disabled }) {
  const words = wordsOf(code);
  return (
    <div className="flex flex-wrap items-center gap-2 font-mono text-sm">
      {words.map((word, index) => {
        const blank = blanks.find((item) => item.index === index + 1);
        if (!blank) {
          return <span key={`${word}-${index}`}>{word}</span>;
        }
        const key = String(blank.index);
        return (
          <input
            key={key}
            aria-label={`Blank ${blank.index}`}
            value={values[key] || ""}
            disabled={disabled}
            placeholder={blank.placeholder || "__"}
            onChange={(event) => onChange({ ...values, [key]: event.target.value })}
            className="w-24 rounded-lg border border-muted/30 bg-bg px-2 py-1 text-text outline-none focus:border-accent disabled:opacity-60"
          />
        );
      })}
    </div>
  );
}
