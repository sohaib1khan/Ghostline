import { EditorState, Prec } from "@codemirror/state";
import { Decoration, EditorView, drawSelection, keymap, WidgetType } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useMemo, useRef, useState } from "react";
import { playSound } from "../../sounds.js";

class GhostWidget extends WidgetType {
  constructor(text) {
    super();
    this.text = text;
  }

  toDOM() {
    const span = document.createElement("span");
    span.className = "ghost-text";
    span.textContent = this.text;
    return span;
  }

  ignoreEvent() {
    return true;
  }
}

function sharedPrefix(target, typed) {
  const limit = Math.min(target.length, typed.length);
  let index = 0;
  while (index < limit && target[index] === typed[index]) {
    index += 1;
  }
  return index;
}

function traceAllowed(target, next) {
  if (next.length > target.length + 1) {
    return false;
  }
  const correct = sharedPrefix(target, next);
  if (correct === next.length) {
    return true;
  }
  return correct === next.length - 1 && correct < target.length;
}

function indentFromGhost(target, current) {
  if (!target) {
    return "  ";
  }
  if (!target.startsWith(current)) {
    return "";
  }
  const match = /^[ \t]+/.exec(target.slice(current.length));
  return match ? match[0] : "";
}

function tokenAt(code, tokens, typedLength) {
  let from = 0;
  for (const token of tokens || []) {
    const index = code.indexOf(token.match, from);
    if (index < 0) {
      continue;
    }
    const end = index + token.match.length;
    if (typedLength >= index && typedLength <= end) {
      return token;
    }
    from = end;
  }
  return null;
}

function liveStats(startedAt, correctChars, mistakes) {
  if (!startedAt) {
    return { wpm: 0, accuracy: 100 };
  }
  const minutes = Math.max((Date.now() - startedAt) / 60000, 1 / 60);
  const wpm = Math.min(400, Math.round(correctChars / 5 / minutes));
  const total = correctChars + mistakes;
  const accuracy = total === 0 ? 100 : Math.round((correctChars / total) * 100);
  return { wpm, accuracy };
}

const SETUP = {
  lineNumbers: false,
  foldGutter: false,
  highlightActiveLine: false,
  highlightActiveLineGutter: false,
  autocompletion: false,
  closeBrackets: false,
  closeBracketsKeymap: false,
  completionKeymap: false,
  drawSelection: false,
  syntaxHighlighting: false,
  indentOnInput: false,
  searchKeymap: false,
};

function isScript(text) {
  return Boolean(text) && (text.includes("\n") || text.length > 80);
}

export default function GhostEditor({
  value,
  onChange,
  target = "",
  tokens = [],
  disabled = false,
  onComplete,
}) {
  const notify = useRef(onChange);
  const complete = useRef(onComplete);
  const started = useRef(0);
  const mistakes = useRef(0);
  const finished = useRef(false);
  const previous = useRef("");
  const [stats, setStats] = useState({ wpm: 0, accuracy: 100 });
  notify.current = onChange;
  complete.current = onComplete;
  const script = isScript(target) || isScript(value);

  const extensions = useMemo(() => {
    const locked = Boolean(target);
    return [
      EditorView.editable.of(!disabled),
      // DECISION: a solid CodeMirror caret. The browser caret blinks against
      // ghost text and restarts whenever the selection is pinned to the end.
      drawSelection({ cursorBlinkRate: 0 }),
      EditorView.domEventHandlers({
        paste(event) {
          event.preventDefault();
          return true;
        },
        drop(event) {
          event.preventDefault();
          return true;
        },
      }),
      EditorState.transactionExtender.of((transaction) => {
        if (!transaction.docChanged) {
          return null;
        }
        return { selection: { anchor: transaction.newDoc.length } };
      }),
      EditorState.transactionFilter.of((transaction) => {
        if (!transaction.docChanged) {
          return transaction;
        }
        if (transaction.isUserEvent("input.paste") || transaction.isUserEvent("input.drop")) {
          return [];
        }
        const next = transaction.newDoc.toString();
        if (next.length > 20000) {
          return [];
        }
        if (locked && !traceAllowed(target, next)) {
          return [];
        }
        return transaction;
      }),
      Prec.highest(
        keymap.of([
          {
            key: "Tab",
            run(view) {
              const current = view.state.doc.toString();
              const insert = indentFromGhost(target, current);
              if (!insert) {
                return true;
              }
              const from = current.length;
              view.dispatch({
                changes: { from, insert },
                selection: { anchor: from + insert.length },
              });
              return true;
            },
          },
        ]),
      ),
      EditorView.updateListener.of((update) => {
        if (locked && update.selectionSet && !update.docChanged) {
          const length = update.state.doc.length;
          if (update.state.selection.main.head !== length) {
            queueMicrotask(() => {
              update.view.dispatch({ selection: { anchor: length } });
            });
          }
        }
        if (!update.docChanged) {
          return;
        }
        const next = update.state.doc.toString();
        const grew = next.length > previous.current.length;
        const correct = locked ? sharedPrefix(target, next) : next.length;
        if (locked && grew && target.startsWith(next)) {
          playSound("tick");
        }
        if (!started.current && next.length > 0) {
          started.current = Date.now();
        }
        if (locked && next.length > previous.current.length && next.length > correct) {
          mistakes.current += 1;
        }
        previous.current = next;
        const nextStats = liveStats(started.current, correct, mistakes.current);
        setStats(nextStats);
        notify.current(next, nextStats);
        if (!locked) {
          return;
        }
        if (next !== target) {
          finished.current = false;
          return;
        }
        if (!finished.current) {
          finished.current = true;
          complete.current?.(nextStats);
        }
      }),
      ...(locked
        ? [
            EditorView.decorations.compute(["doc"], (state) => {
              const typed = state.doc.toString();
              const correct = sharedPrefix(target, typed);
              const marks = [];
              if (typed.length === correct + 1) {
                marks.push(Decoration.mark({ class: "ghost-wrong" }).range(correct, typed.length));
              }
              const rest = target.slice(correct);
              if (rest) {
                marks.push(
                  Decoration.widget({ widget: new GhostWidget(rest), side: 1 }).range(typed.length),
                );
              }
              return Decoration.set(marks, true);
            }),
          ]
        : []),
    ];
  }, [disabled, target]);

  const activeToken = target ? tokenAt(target, tokens, sharedPrefix(target, value)) : null;
  const wrong = Boolean(target) && value.length > 0 && !target.startsWith(value);
  const setup = useMemo(
    () => ({
      ...SETUP,
      lineNumbers: script,
    }),
    [script],
  );

  return (
    <div className={wrong ? "ghost-shake" : undefined}>
      {activeToken ? (
        <p className="mb-2 rounded-xl border border-accent/20 bg-bg/80 px-3 py-2 text-sm text-muted">
          {activeToken.explain}
        </p>
      ) : null}
      <div className={`ghost-frame ${script ? "ghost-frame-script" : ""}`}>
        <div className="ghost-frame-chrome" aria-hidden="true">
          <span className="ghost-frame-traffic">
            <span className="ghost-frame-dot" />
            <span className="ghost-frame-dot" />
            <span className="ghost-frame-dot" />
          </span>
          <span className="ghost-frame-title">Ghostline · Trace</span>
          <span className="ghost-frame-badge">live</span>
        </div>
        <div className="ghost-frame-body">
          <CodeMirror
            value={value}
            basicSetup={setup}
            extensions={extensions}
            editable={!disabled}
            indentWithTab={false}
            onChange={() => {}}
            theme="none"
          />
        </div>
      </div>
      <p className="ghost-stats">
        <strong>{stats.wpm}</strong> wpm · <strong>{stats.accuracy}</strong>%
      </p>
    </div>
  );
}
