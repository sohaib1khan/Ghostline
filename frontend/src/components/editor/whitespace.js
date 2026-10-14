/** Quiet indent guides: soft · for spaces, thin rail at each indent level. */

import { Decoration, EditorView } from "@codemirror/view";

function leadingWidth(lineText) {
  let width = 0;
  for (const ch of lineText) {
    if (ch === " ") {
      width += 1;
    } else if (ch === "\t") {
      width += 4;
    } else {
      break;
    }
  }
  return width;
}

/**
 * Decorate leading whitespace so nesting is readable without visual noise.
 * @param {number} indentUnit
 */
export function whitespaceGuides(indentUnit = 4) {
  const unit = Math.max(2, indentUnit || 4);

  return EditorView.decorations.compute(["doc"], (state) => {
    const marks = [];
    for (let lineNumber = 1; lineNumber <= state.doc.lines; lineNumber += 1) {
      const line = state.doc.line(lineNumber);
      const text = line.text;
      let col = 0;
      for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];
        const from = line.from + i;
        if (ch === " ") {
          const atUnit = col % unit === 0;
          marks.push(
            Decoration.mark({
              class: atUnit ? "ws-space ws-guide" : "ws-space",
            }).range(from, from + 1),
          );
          col += 1;
          continue;
        }
        if (ch === "\t") {
          marks.push(Decoration.mark({ class: "ws-tab ws-guide" }).range(from, from + 1));
          col += unit;
          continue;
        }
        break;
      }
    }
    return Decoration.set(marks, true);
  });
}

export function indentDepth(text, indentUnit = 4) {
  const unit = Math.max(2, indentUnit || 4);
  const lines = String(text || "").split("\n");
  const last = lines[lines.length - 1] || "";
  const width = leadingWidth(last);
  return {
    spaces: width,
    level: Math.floor(width / unit),
    unit,
  };
}
