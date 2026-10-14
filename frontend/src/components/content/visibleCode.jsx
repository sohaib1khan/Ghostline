/** Turn leading spaces/tabs into visible · / ⇥ marks for any code display. */

import { Children, isValidElement } from "react";

function markLeading(text) {
  const raw = String(text ?? "");
  if (!raw) {
    return raw;
  }
  const out = [];
  let i = 0;
  let lineStart = true;
  let key = 0;
  while (i < raw.length) {
    const ch = raw[i];
    if (ch === "\n") {
      out.push("\n");
      lineStart = true;
      i += 1;
      continue;
    }
    if (lineStart && (ch === " " || ch === "\t")) {
      out.push(
        <span key={`v-${key++}`} className={ch === "\t" ? "ws-ex-tab" : "ws-ex-space"} aria-hidden="true">
          {ch === "\t" ? "⇥" : "·"}
        </span>,
      );
      i += 1;
      continue;
    }
    lineStart = false;
    let end = i + 1;
    while (end < raw.length && raw[end] !== "\n") {
      end += 1;
    }
    out.push(raw.slice(i, end));
    i = end;
  }
  return out;
}

function flattenText(node) {
  if (node == null || typeof node === "boolean") {
    return "";
  }
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(flattenText).join("");
  }
  if (isValidElement(node)) {
    return flattenText(node.props?.children);
  }
  return "";
}

/** Map react-markdown / DOM children into space-visible nodes. */
export function visibleCodeChildren(children) {
  const text = flattenText(Children.toArray(children));
  if (!text.includes(" ") && !text.includes("\t")) {
    return children;
  }
  return markLeading(text);
}
