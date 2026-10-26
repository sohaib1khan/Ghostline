import { useEffect, useRef, useState } from "react";

function toLines(source) {
  if (Array.isArray(source)) {
    return source.map(String);
  }
  return String(source || "")
    .split("\n")
    .filter((line, index, all) => line.trim() !== "" || index < all.length - 1);
}

/** Deterministic shuffle (seeded by the text) so a refresh doesn't reshuffle mid-attempt. */
function shuffled(lines) {
  let seed = 0;
  for (const char of lines.join("\n")) {
    seed = (seed * 31 + char.charCodeAt(0)) >>> 0;
  }
  const order = lines.map((_, index) => index);
  for (let i = order.length - 1; i > 0; i -= 1) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    const j = seed % (i + 1);
    [order[i], order[j]] = [order[j], order[i]];
  }
  // Never hand back the solved order.
  if (order.length > 1 && order.every((value, index) => value === index)) {
    order.push(order.shift());
  }
  return order.map((index) => ({ id: index, text: lines[index] }));
}

/**
 * Parsons puzzle — put the shuffled lines in order.
 * Keyboard: Tab to a line, Enter/Space picks it up, ArrowUp/ArrowDown moves it, Enter/Space/Escape drops it.
 * Without picking up, ArrowUp/ArrowDown just moves focus. Up/Down buttons cover touch.
 */
/** Rebuild saved order from joined text, or null if it isn't a permutation of the source lines. */
function rebuild(lines, value) {
  if (!value || value.split("\n").length !== lines.length) {
    return null;
  }
  const pool = lines.map((text, id) => ({ id, text }));
  const out = [];
  for (const text of value.split("\n")) {
    const at = pool.findIndex((item) => item.text === text);
    if (at === -1) {
      return null;
    }
    out.push(pool.splice(at, 1)[0]);
  }
  return out;
}

export default function ParsonsPuzzle({ lines, value, onChange, disabled = false, label }) {
  const source = toLines(lines);
  const key = source.join("\n");
  const [items, setItems] = useState(() => rebuild(source, value) || shuffled(source));
  const [grabbed, setGrabbed] = useState(null);
  const [announce, setAnnounce] = useState("");
  const refs = useRef(new Map());
  const focusId = useRef(null);
  const first = useRef(true);
  const notify = useRef(onChange);
  notify.current = onChange;

  useEffect(() => {
    if (first.current) {
      first.current = false;
      // Report the starting order (restored or shuffled) so the parent always has an answer.
      notify.current?.(items.map((item) => item.text).join("\n"));
      return;
    }
    const next = shuffled(toLines(lines));
    setItems(next);
    setGrabbed(null);
    notify.current?.(next.map((item) => item.text).join("\n"));
    // `key` captures the content; `lines` identity alone would reshuffle on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (focusId.current !== null) {
      refs.current.get(focusId.current)?.focus();
      focusId.current = null;
    }
  });

  function commit(next, movedId, position) {
    setItems(next);
    focusId.current = movedId;
    setAnnounce(`${next.find((item) => item.id === movedId)?.text.trim() || "Line"} moved to position ${position + 1} of ${next.length}`);
    onChange?.(next.map((item) => item.text).join("\n"));
  }

  function move(id, delta) {
    const from = items.findIndex((item) => item.id === id);
    const to = from + delta;
    if (from === -1 || to < 0 || to >= items.length) {
      return;
    }
    const next = [...items];
    const [picked] = next.splice(from, 1);
    next.splice(to, 0, picked);
    commit(next, id, to);
  }

  function focusAt(index) {
    const target = items[Math.max(0, Math.min(items.length - 1, index))];
    refs.current.get(target.id)?.focus();
  }

  function onKeyDown(event, id, index) {
    if (disabled) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (grabbed === id) {
        setGrabbed(null);
        setAnnounce("Dropped");
      } else {
        setGrabbed(id);
        setAnnounce("Picked up. Use arrow up or down to move, Enter to drop.");
      }
    } else if (event.key === "Escape" && grabbed !== null) {
      event.preventDefault();
      setGrabbed(null);
      setAnnounce("Dropped");
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      const delta = event.key === "ArrowUp" ? -1 : 1;
      if (grabbed === id) {
        move(id, delta);
      } else {
        focusAt(index + delta);
      }
    }
  }

  return (
    <div>
      <p className="text-sm text-muted" id="parsons-help">
        {label || "Put the lines in the right order."} Press Enter to pick up a line, arrow keys to
        move it, Enter to drop. Or use the Up / Down buttons.
      </p>
      <ol className="mt-3 flex flex-col gap-2" aria-describedby="parsons-help">
        {items.map((item, index) => {
          const active = grabbed === item.id;
          return (
            <li key={item.id} className="flex items-stretch gap-2">
              <button
                type="button"
                ref={(node) => {
                  if (node) {
                    refs.current.set(item.id, node);
                  } else {
                    refs.current.delete(item.id);
                  }
                }}
                disabled={disabled}
                aria-pressed={active}
                aria-label={`Line ${index + 1} of ${items.length}: ${item.text.trim() || "blank line"}${active ? ", picked up" : ""}`}
                onKeyDown={(event) => onKeyDown(event, item.id, index)}
                onClick={() => setGrabbed(active ? null : item.id)}
                className={`min-h-11 min-w-0 flex-1 rounded-xl border px-3 py-2 text-left font-mono text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                  active ? "border-accent bg-accent/15" : "border-muted/30 bg-bg"
                }`}
              >
                <span className="whitespace-pre-wrap break-words">{item.text || " "}</span>
              </button>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="min-h-11 min-w-11 rounded-xl border border-muted/30 text-sm text-muted disabled:opacity-40"
                  disabled={disabled || index === 0}
                  aria-label={`Move line ${index + 1} up`}
                  onClick={() => move(item.id, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="min-h-11 min-w-11 rounded-xl border border-muted/30 text-sm text-muted disabled:opacity-40"
                  disabled={disabled || index === items.length - 1}
                  aria-label={`Move line ${index + 1} down`}
                  onClick={() => move(item.id, 1)}
                >
                  ↓
                </button>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="sr-only" role="status" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
