import { wordsOf } from "./fill.js";

export default function FillGap({ code, blanks, values, onChange, disabled }) {
  const words = wordsOf(code);
  return (
    <div className="ghost-frame">
      <div className="ghost-frame-chrome" aria-hidden="true">
        <span className="ghost-frame-traffic">
          <span className="ghost-frame-dot" />
          <span className="ghost-frame-dot" />
          <span className="ghost-frame-dot" />
        </span>
        <span className="ghost-frame-title">Ghostline · Fill</span>
        <span className="ghost-frame-badge">blanks</span>
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
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              // Spaces and punctuation in answers must stay as typed.
              onChange={(event) => onChange({ ...values, [key]: event.target.value })}
              onKeyDown={(event) => {
                if (event.key !== " " && event.key !== "Tab") {
                  return;
                }
                // Keep Space in the blank; Tab moves to the next blank without leaving the frame.
                if (event.key === " ") {
                  return;
                }
                event.preventDefault();
                const inputs = event.currentTarget
                  .closest(".fill-frame")
                  ?.querySelectorAll("input.fill-blank:not(:disabled)");
                if (!inputs?.length) {
                  return;
                }
                const list = Array.from(inputs);
                const at = list.indexOf(event.currentTarget);
                const next = list[event.shiftKey ? at - 1 : at + 1];
                next?.focus();
              }}
              className="fill-blank"
            />
          );
        })}
      </div>
    </div>
  );
}
