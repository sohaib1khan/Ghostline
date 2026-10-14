/** Visible spaces, tabs, and indent depth marks for low-vision typing. */

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
 * Decorate leading whitespace so spaces and tabs are visible.
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
      let i = 0;
      for (; i < text.length; i += 1) {
        const ch = text[i];
        const from = line.from + i;
        if (ch === " ") {
          const guide = col % unit === 0;
          marks.push(
            Decoration.mark({
              class: guide ? "ws-space ws-space-guide" : "ws-space",
            }).range(from, from + 1),
          );
          col += 1;
          continue;
        }
        if (ch === "\t") {
          marks.push(Decoration.mark({ class: "ws-tab" }).range(from, from + 1));
          col += unit;
          continue;
        }
        break;
      }
      const depth = leadingWidth(text);
      const level = Math.floor(depth / unit);
      if (text.trim() && level > 0 && i < text.length) {
        marks.push(
          Decoration.mark({
            class: `ws-indent-edge ws-indent-l${Math.min(8, level)}`,
          }).range(line.from + i, line.from + i + 1),
        );
      }
      if (level > 0) {
        marks.push(
          Decoration.line({
            class: `ws-line-indent ws-line-l${Math.min(8, level)}`,
          }).range(line.from),
        );
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
