/** Free CodeMirror field with visible spaces/indents — playground and any free IDE. */

import CodeMirror from "@uiw/react-codemirror";
import { EditorView, keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import { useEffect, useMemo, useRef, useState } from "react";
import { bumpTypingScale, readPrefs, writePrefs } from "../../prefs.js";
import { indentDepth, whitespaceGuides } from "./whitespace.js";

const SETUP = {
  lineNumbers: true,
  foldGutter: false,
  highlightActiveLine: true,
  highlightActiveLineGutter: true,
  autocompletion: false,
  closeBrackets: false,
  closeBracketsKeymap: false,
  completionKeymap: false,
  syntaxHighlighting: false,
  indentOnInput: false,
  searchKeymap: false,
};

const SCALE_LABEL = { md: "M", lg: "L", xl: "XL" };

function leadingIndent(text) {
  const lines = String(text || "").split("\n");
  const last = lines[lines.length - 1] || "";
  const match = /^[ \t]*/.exec(last);
  return match ? match[0] : "";
}

export default function VisibleCodeField({
  value,
  onChange,
  indentUnit = 4,
  disabled = false,
  className = "",
}) {
  const [prefs, setPrefs] = useState(readPrefs);
  const unit = Math.max(2, Number(indentUnit) || 4);
  const showSpaces = prefs.showWhitespace !== false;
  const indent = indentDepth(value, unit);
  const viewRef = useRef(null);

  useEffect(() => {
    function sync() {
      setPrefs(readPrefs());
    }
    window.addEventListener("ghostline-prefs", sync);
    return () => window.removeEventListener("ghostline-prefs", sync);
  }, []);

  const extensions = useMemo(() => {
    return [
      EditorView.editable.of(!disabled),
      Prec.highest(
        keymap.of([
          {
            key: "Tab",
            run(view) {
              const pad = " ".repeat(unit);
              view.dispatch(view.state.replaceSelection(pad));
              return true;
            },
          },
          {
            key: "Enter",
            run(view) {
              const { from } = view.state.selection.main;
              const before = view.state.doc.sliceString(0, from);
              const indent = leadingIndent(before);
              view.dispatch(view.state.replaceSelection(`\n${indent}`));
              return true;
            },
          },
        ]),
      ),
      ...(showSpaces ? [whitespaceGuides(unit)] : []),
    ];
  }, [disabled, unit, showSpaces]);

  const lines = String(value || "").split("\n");
  const caretLine = lines.length;
  const caretCol = (lines[lines.length - 1] || "").length + 1;

  return (
    <div className={`ghost-ide ${className}`.trim()}>
      <div className="ghost-frame ghost-frame-script">
        <div className="ghost-frame-chrome">
          <span className="ghost-frame-traffic" aria-hidden="true">
            <span className="ghost-frame-dot" />
            <span className="ghost-frame-dot" />
            <span className="ghost-frame-dot" />
          </span>
          <span className="ghost-frame-title">editor · playground</span>
          <div className="ghost-vision-tools" role="group" aria-label="Typing size and spaces">
            <button
              type="button"
              className="ghost-vision-btn"
              aria-label="Smaller typing"
              title="Smaller typing"
              disabled={prefs.typingScale === "md"}
              onClick={() => setPrefs(bumpTypingScale(-1))}
            >
              A−
            </button>
            <span className="ghost-vision-scale" aria-live="polite">
              {SCALE_LABEL[prefs.typingScale] || "L"}
            </span>
            <button
              type="button"
              className="ghost-vision-btn"
              aria-label="Larger typing"
              title="Larger typing"
              disabled={prefs.typingScale === "xl"}
              onClick={() => setPrefs(bumpTypingScale(1))}
            >
              A+
            </button>
            <button
              type="button"
              className={`ghost-vision-btn ${showSpaces ? "ghost-vision-btn-on" : ""}`}
              aria-label={showSpaces ? "Hide space marks" : "Show space marks"}
              aria-pressed={showSpaces}
              title={showSpaces ? "Hide · space marks" : "Show · space marks"}
              onClick={() => setPrefs(writePrefs({ ...prefs, showWhitespace: !showSpaces }))}
            >
              ··
            </button>
          </div>
          <span className="ghost-frame-badge" aria-hidden="true">
            live
          </span>
        </div>
        <div className="ghost-type-actions">
          <span className="ghost-type-action-hint">
            Enter keeps indent · Tab inserts {unit} spaces · · marks show nesting
          </span>
        </div>
        <div className="ghost-frame-body playground-cm-body">
          <CodeMirror
            value={value}
            basicSetup={SETUP}
            extensions={extensions}
            editable={!disabled}
            indentWithTab={false}
            onCreateEditor={(view) => {
              viewRef.current = view;
            }}
            onChange={(next) => onChange?.(next)}
            theme="none"
          />
        </div>
        <div className="ghost-ide-statusbar" aria-live="polite">
          <span>
            Ln <strong>{caretLine}</strong> · Col <strong>{caretCol}</strong>
          </span>
          <span
            className={`ghost-indent-meter ${indent.level > 0 ? "ghost-indent-meter-on" : ""}`}
            title={`${indent.spaces} leading spaces · level ${indent.level} (${indent.unit}-space)`}
          >
            indent <strong>{indent.level}</strong>
            <span className="ghost-indent-bars" aria-hidden="true">
              {Array.from({ length: Math.min(8, Math.max(0, indent.level)) }, (_, i) => (
                <span key={i} className="ghost-indent-bar" />
              ))}
            </span>
            <span className="ghost-indent-spaces">{indent.spaces} sp</span>
          </span>
          <span className="ghost-indent-spaces">{unit}-space tab</span>
        </div>
      </div>
    </div>
  );
}
