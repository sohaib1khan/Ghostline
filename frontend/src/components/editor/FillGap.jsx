import { wordsOf } from "./fill.js";

export default function FillGap({ code, blanks, values, onChange, disabled }) {
  const words = wordsOf(code);
  return (
    <div className="ghost-frame">
      <div className="ghost-frame-chrome" aria-hidden="true">
        <span className="ghost-frame-dot" />
        <span>fill // blanks</span>
      </div>
      <div className="ghost-frame-body fill-frame">
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
              className="fill-blank"
            />
          );
        })}
      </div>
    </div>
  );
}
