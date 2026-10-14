import { wordsOf } from "./fill.js";

export default function FillGap({ code, blanks, values, onChange, disabled }) {
  const words = wordsOf(code);
  return (
    <div className="ghost-ide">
    <div className="ghost-frame">
      <div className="ghost-frame-chrome" aria-hidden="true">
        <span className="ghost-frame-traffic">
          <span className="ghost-frame-dot" />
          <span className="ghost-frame-dot" />
          <span className="ghost-frame-dot" />
        </span>
        <span className="ghost-frame-title">editor · fill blanks</span>
        <span className="ghost-frame-badge">blanks</span>
      </div>
      <div className="ghost-frame-body fill-frame">
        {words.map((word, index) => {
          const blank = blanks.find((item) => item.index === index + 1);
          const gap =
            index > 0 ? (
              <span key={`gap-${index}`} className="fill-space-mark" aria-hidden="true">
                ·
              </span>
            ) : null;
          if (!blank) {
            return (
              <span key={`${word}-${index}`}>
                {gap}
                <span className="fill-word">{word}</span>
              </span>
            );
          }
          const key = String(blank.index);
          return (
            <span key={key}>
              {gap}
              <input
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
            </span>
          );
        })}
      </div>
    </div>
    </div>
  );
}
