import { EditorState, Prec } from "@codemirror/state";
import { Decoration, EditorView, drawSelection, keymap, WidgetType } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useEffect, useMemo, useRef, useState } from "react";
import { bumpTypingScale, readPrefs, writePrefs } from "../../prefs.js";
import { playSound } from "../../sounds.js";
import { indentDepth, whitespaceGuides } from "./whitespace.js";

class TypeMarkerWidget extends WidgetType {
  toDOM() {
    const span = document.createElement("span");
    span.className = "ghost-type-marker";
    span.setAttribute("aria-hidden", "true");
    span.title = "Your typing cursor";
    return span;
  }

  ignoreEvent() {
    return true;
  }

  eq() {
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

function lastLineIndent(text) {
  const lineStart = text.lastIndexOf("\n") + 1;
  const match = /^[ \t]*/.exec(text.slice(lineStart));
  return match ? match[0] : "";
}

/** Free typing: newline, then keep the current line's indent. */
function freeEnterInsert(current) {
  return `\n${lastLineIndent(current)}`;
}

/** Enter (locked): one newline, then auto-indent from the ghost (stop before another blank). */
function enterInsert(target, current) {
  if (!target) {
    return freeEnterInsert(current);
  }
  if (!target.startsWith(current)) {
    return "";
  }
  const rest = target.slice(current.length);
  if (!rest.startsWith("\n")) {
    return "";
  }
  let insert = "\n";
  let index = 1;
  while (index < rest.length && (rest[index] === " " || rest[index] === "\t")) {
    insert += rest[index];
    index += 1;
  }
  return insert;
}

/** Insert the next run of spaces/tabs/newlines until the next visible character. */
function whitespaceInsert(target, current) {
  if (!target || !target.startsWith(current)) {
    return "";
  }
  const rest = target.slice(current.length);
  let index = 0;
  while (index < rest.length && (rest[index] === " " || rest[index] === "\t" || rest[index] === "\n")) {
    index += 1;
  }
  return rest.slice(0, index);
}

function tabInsert(target, current, indentUnit = 4) {
  const pad = " ".repeat(Math.max(2, indentUnit || 4));
  if (target && target.startsWith(current)) {
    return indentFromGhost(target, current) || whitespaceInsert(target, current) || pad;
  }
  return pad;
}

function dispatchInsert(view, insert) {
  if (!insert) {
    return false;
  }
  const from = view.state.doc.length;
  view.dispatch({
    changes: { from, insert },
    selection: { anchor: from + insert.length },
  });
  return true;
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
    return { wpm: 0, accuracy: 100, duration_seconds: 0 };
  }
  const elapsedMs = Date.now() - startedAt;
  const minutes = Math.max(elapsedMs / 60000, 1 / 60);
  const wpm = Math.min(400, Math.round(correctChars / 5 / minutes));
  const total = correctChars + mistakes;
  const accuracy = total === 0 ? 100 : Math.round((correctChars / total) * 100);
  const duration_seconds = Math.min(86_400, Math.max(1, Math.round(elapsedMs / 1000)));
  return { wpm, accuracy, duration_seconds };
}

function displayChar(char) {
  if (char === "\n") {
    return "↵ return";
  }
  if (char === " ") {
    return "space";
  }
  if (char === "\t") {
    return "tab";
  }
  return char;
}

/** Stable line-by-line progress — guide stays put; editor only shows typed text. */
function lineGuide(target, typed) {
  if (!target) {
    return null;
  }
  const lines = target.split("\n");
  const correct = sharedPrefix(target, typed);
  let offset = 0;
  let lineIndex = 0;
  for (let index = 0; index < lines.length; index += 1) {
    const withBreak = lines[index].length + (index < lines.length - 1 ? 1 : 0);
    if (correct < offset + withBreak || index === lines.length - 1) {
      lineIndex = index;
      break;
    }
    offset += withBreak;
  }
  const line = lines[lineIndex] || "";
  const col = Math.min(Math.max(0, correct - offset), line.length);
  const needsReturn = col >= line.length && lineIndex < lines.length - 1;
  const nextChar = needsReturn ? "\n" : line[col] || "";
  return {
    lines,
    lineIndex,
    lineCount: lines.length,
    line,
    col,
    done: line.slice(0, col),
    nextChar,
    rest: needsReturn ? "" : line.slice(col + (nextChar ? 1 : 0)),
    prevLine: lineIndex > 0 ? lines[lineIndex - 1] : null,
    nextLine: lineIndex < lines.length - 1 ? lines[lineIndex + 1] : null,
    complete: correct >= target.length,
  };
}

const SETUP = {
  lineNumbers: false,
  foldGutter: false,
  highlightActiveLine: true,
  highlightActiveLineGutter: true,
  autocompletion: false,
  closeBrackets: false,
  closeBracketsKeymap: false,
  completionKeymap: false,
  drawSelection: false,
  syntaxHighlighting: false,
  indentOnInput: false,
  searchKeymap: false,
};

const SCALE_LABEL = { md: "M", lg: "L", xl: "XL" };

function isScript(text) {
  return Boolean(text) && (text.includes("\n") || text.length > 80);
}

function LineHelper({ guide }) {
  const scroller = useRef(null);
  const currentRow = useRef(null);

  useEffect(() => {
    if (!currentRow.current) {
      return;
    }
    currentRow.current.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [guide?.lineIndex]);

  if (!guide) {
    return null;
  }
  const label = displayChar(guide.nextChar);
  return (
    <div className="line-helper">
      <div className="line-helper-meta">
        <span className="line-helper-step">
          Line {Math.min(guide.lineIndex + 1, guide.lineCount)} of {guide.lineCount}
        </span>
        {!guide.complete && guide.nextChar ? (
          <span className="line-helper-key" title="Next key to press">
            Next: <kbd>{label}</kbd>
          </span>
        ) : (
          <span className="line-helper-key line-helper-key-done">Line clear</span>
        )}
      </div>
      <div className="line-helper-scroll" ref={scroller} role="list">
        {guide.lines.map((line, index) => {
          const done = index < guide.lineIndex;
          const current = index === guide.lineIndex && !guide.complete;
          let rowClass = "line-helper-row line-helper-upcoming";
          if (done) {
            rowClass = "line-helper-row line-helper-prev";
          } else if (current) {
            rowClass = "line-helper-row line-helper-current";
          }
          return (
            <p
              key={`guide-line-${index}`}
              className={rowClass}
              role="listitem"
              ref={current ? currentRow : undefined}
              aria-current={current ? "step" : undefined}
            >
              <span className="line-helper-gutter" aria-hidden="true">
                {index + 1}
              </span>
              <span className="line-helper-mark" aria-hidden="true">
                {done ? "✓" : current ? "▸" : "·"}
              </span>
              <code>
                {current ? (
                  <>
                    <span className="line-helper-done">{guide.done}</span>
                    {guide.nextChar && guide.nextChar !== "\n" ? (
                      <span className="line-helper-next">{guide.nextChar}</span>
                    ) : null}
                    {guide.nextChar === "\n" ? (
                      <span className="line-helper-next line-helper-return">↵</span>
                    ) : null}
                    <span className="line-helper-rest">{guide.rest}</span>
                    {!guide.line && guide.nextChar === "\n" ? (
                      <span className="line-helper-blank"> (blank line — press Enter)</span>
                    ) : null}
                  </>
                ) : line ? (
                  line
                ) : (
                  <span className="line-helper-blank">(blank line)</span>
                )}
              </code>
            </p>
          );
        })}
      </div>
    </div>
  );
}

export default function GhostEditor({
  value,
  onChange,
  target = "",
  /** Soft guide text (hint ghost) — shows LineHelper without locking free typing. */
  ghost = "",
  tokens = [],
  disabled = false,
  onComplete,
  indentUnit = 4,
}) {
  const notify = useRef(onChange);
  const complete = useRef(onComplete);
  const started = useRef(0);
  const mistakes = useRef(0);
  const finished = useRef(false);
  const previous = useRef("");
  const [stats, setStats] = useState({ wpm: 0, accuracy: 100, duration_seconds: 0 });
  const [prefs, setPrefs] = useState(readPrefs);
  const viewRef = useRef(null);
  const unit = Math.max(2, Number(indentUnit) || 4);
  notify.current = onChange;
  complete.current = onComplete;
  // Trace locks to `target`. Hint ghost guides with `ghost` but still allows free typing + Check.
  const guideText = target || ghost || "";
  const locked = Boolean(target);
  const guided = Boolean(guideText);
  const onPath = guided && guideText.startsWith(value);
  const script = isScript(guideText) || isScript(value);
  const guide = useMemo(
    () => (guided ? lineGuide(guideText, value) : null),
    [guided, guideText, value],
  );
  const nextIsEnter = guided && onPath ? guide?.nextChar === "\n" : !guided;
  const nextIsIndent = guided && onPath
    ? guide?.nextChar === " " ||
      guide?.nextChar === "\t" ||
      Boolean(indentFromGhost(guideText, value))
    : !guided;
  const canFillWhitespace = guided && onPath && Boolean(whitespaceInsert(guideText, value));
  // Every practice typing box gets Enter/Tab helpers — locked/ghost fills from the guide; free keeps indent.
  const showTypeActions = !disabled;
  const caretLine = guide ? guide.lineIndex + 1 : value.split("\n").length;
  const caretCol = guide ? guide.col + 1 : (value.split("\n").pop() || "").length + 1;
  const indent = indentDepth(value, unit);
  const showSpaces = prefs.showWhitespace !== false;

  useEffect(() => {
    function sync() {
      setPrefs(readPrefs());
    }
    window.addEventListener("ghostline-prefs", sync);
    return () => window.removeEventListener("ghostline-prefs", sync);
  }, []);

  function changeScale(delta) {
    setPrefs(bumpTypingScale(delta));
    queueMicrotask(() => viewRef.current?.focus());
  }

  function runEditorInsert(builder) {
    const view = viewRef.current;
    if (!view || disabled) {
      return;
    }
    const current = view.state.doc.toString();
    dispatchInsert(view, builder(guideText, current));
    view.focus();
  }

  const extensions = useMemo(() => {
    return [
      EditorView.editable.of(!disabled),
      // DECISION: solid caret. Guide lives outside the editor so typing stays calm.
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
            key: "Enter",
            run(view) {
              const current = view.state.doc.toString();
              const insert = enterInsert(guideText, current);
              if (locked) {
                // Always consume Enter in locked mode so a wrong newline never slips in.
                dispatchInsert(view, insert);
                return true;
              }
              dispatchInsert(view, insert || freeEnterInsert(current));
              return true;
            },
          },
          {
            key: "Tab",
            run(view) {
              const current = view.state.doc.toString();
              const insert = tabInsert(guideText, current, unit);
              dispatchInsert(view, insert);
              return true;
            },
          },
        ]),
      ),
      ...(showSpaces ? [whitespaceGuides(unit)] : []),
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
          if (!disabled) {
            complete.current?.(nextStats);
          }
        }
      }),
      // Thick typing marker at the caret — always on so low-vision users can find their place.
      EditorView.decorations.compute(["doc", "selection"], (state) => {
        const typed = state.doc.toString();
        const marks = [];
        if (locked && typed.length === sharedPrefix(target, typed) + 1) {
          const correct = sharedPrefix(target, typed);
          marks.push(Decoration.mark({ class: "ghost-wrong" }).range(correct, typed.length));
        }
        if (!disabled) {
          const head = locked ? typed.length : state.selection.main.head;
          marks.push(
            Decoration.widget({ widget: new TypeMarkerWidget(), side: 1 }).range(head),
          );
        }
        return Decoration.set(marks, true);
      }),
    ];
  }, [disabled, locked, target, guideText, unit, showSpaces]);

  const activeToken = guideText
    ? tokenAt(guideText, tokens, sharedPrefix(guideText, value))
    : null;
  const wrong = locked && value.length > 0 && !target.startsWith(value);
  const hintGhost = Boolean(ghost) && !locked;
  const setup = useMemo(
    () => ({
      ...SETUP,
      lineNumbers: script,
    }),
    [script],
  );

  return (
    <div className={`ghost-ide ${wrong ? "ghost-shake" : ""}`}>
      {activeToken ? (
        <p className="ghost-ide-tip mb-2 rounded-xl border border-accent/20 bg-bg/80 px-3 py-2 text-sm text-muted">
          {activeToken.explain}
        </p>
      ) : null}
      {hintGhost ? (
        <p className="ghost-hint-banner mb-2" role="status">
          Hint ghost on — bright letter is next. Type it, or use Tab / Enter when they light up.
        </p>
      ) : null}
      {guide ? <LineHelper guide={guide} /> : null}
      <div className={`ghost-frame ${script ? "ghost-frame-script" : ""}`}>
        <div className="ghost-frame-chrome">
          <span className="ghost-frame-traffic" aria-hidden="true">
            <span className="ghost-frame-dot" />
            <span className="ghost-frame-dot" />
            <span className="ghost-frame-dot" />
          </span>
          <span className="ghost-frame-title">
            {hintGhost ? "editor · hint ghost" : "editor · your typing"}
          </span>
          <div className="ghost-vision-tools" role="group" aria-label="Typing size and spaces">
            <button
              type="button"
              className="ghost-vision-btn"
              aria-label="Smaller typing"
              title="Smaller typing"
              disabled={prefs.typingScale === "md"}
              onClick={() => changeScale(-1)}
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
              onClick={() => changeScale(1)}
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
        {showTypeActions ? (
          <div className="ghost-type-actions">
            <button
              type="button"
              className={`ghost-type-action ${guided && onPath && nextIsEnter ? "ghost-type-action-hot" : ""}`}
              disabled={disabled || (locked && !nextIsEnter)}
              onClick={() => runEditorInsert(enterInsert)}
            >
              Enter ↵
            </button>
            <button
              type="button"
              className={`ghost-type-action ${
                guided && onPath && nextIsIndent && !nextIsEnter ? "ghost-type-action-hot" : ""
              }`}
              disabled={disabled || (locked && !nextIsIndent && !canFillWhitespace)}
              onClick={() => runEditorInsert((t, c) => tabInsert(t, c, unit))}
            >
              Tab indent
            </button>
            {guided && onPath ? (
              <button
                type="button"
                className="ghost-type-action"
                disabled={disabled || !canFillWhitespace}
                onClick={() => runEditorInsert(whitespaceInsert)}
                title="Insert spaces, tabs, and blank lines until the next character"
              >
                Fill spaces
              </button>
            ) : null}
            <span className="ghost-type-action-hint">
              {guided && onPath
                ? nextIsEnter
                  ? "Press Enter — blank lines and indent are included when needed"
                  : nextIsIndent
                    ? "Press Tab or Space for indentation"
                    : "Type the highlighted key from the guide"
                : guided
                  ? "Backspace to the matching prefix to rejoin the ghost line"
                  : `Enter keeps indent · Tab inserts ${unit} spaces`}
            </span>
          </div>
        ) : null}
        <div className="ghost-frame-body">
          {!value && !disabled ? (
            <p className="ghost-caret-hint" aria-hidden="true">
              Thick bar marks where you type
            </p>
          ) : null}
          <CodeMirror
            value={value}
            basicSetup={setup}
            extensions={extensions}
            editable={!disabled}
            indentWithTab={false}
            onCreateEditor={(view) => {
              viewRef.current = view;
              if (!disabled) {
                queueMicrotask(() => view.focus());
              }
            }}
            onChange={() => {}}
            theme="none"
          />
        </div>
        <div className="ghost-ide-statusbar" aria-live="polite">
          <span className="ghost-caret-legend">
            <span className="ghost-type-marker ghost-type-marker-inline" aria-hidden="true" />
            caret
          </span>
          <span>
            Ln <strong>{caretLine}</strong> · Col <strong>{caretCol}</strong>
          </span>
          <span
            className={`ghost-indent-meter ${indent.level > 0 ? "ghost-indent-meter-on" : ""}`}
            title={`${indent.spaces} spaces · ${indent.unit}-space indent`}
          >
            Level <strong>{indent.level}</strong>
            <span aria-hidden="true">·</span>
            <span>{indent.spaces} spaces</span>
          </span>
          <span>
            <strong>{stats.wpm}</strong> wpm · <strong>{stats.accuracy}</strong>%
          </span>
        </div>
      </div>
    </div>
  );
}
