import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

/**
 * Guided study step before recall/challenge. Lines reveal, then the learner starts.
 */
export default function WorkedExample({
  code = "",
  tokens = [],
  title = "Worked example",
  onStart,
  reduceMotion = false,
}) {
  const systemReduce = useReducedMotion();
  const reduce = reduceMotion || Boolean(systemReduce);
  const lines = String(code || "").split("\n");
  const [shown, setShown] = useState(reduce ? lines.length : 0);
  const done = shown >= lines.length;

  useEffect(() => {
    setShown(reduce ? lines.length : 0);
  }, [code, reduce, lines.length]);

  useEffect(() => {
    if (reduce || shown >= lines.length) {
      return undefined;
    }
    const timer = window.setTimeout(() => setShown((count) => count + 1), 90);
    return () => window.clearTimeout(timer);
  }, [reduce, shown, lines.length]);

  if (!code) {
    return null;
  }

  return (
    <div className="example-panel rounded-xl border border-accent/25 bg-bg/80 p-4">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">{title}</p>
      <p className="mt-1 text-sm text-muted">
        Read it once. Tokens light up as the lines settle — then type it yourself.
      </p>
      <pre className="mt-3 overflow-x-auto font-mono text-sm leading-relaxed">
        {lines.slice(0, shown).map((line, index) => {
          const active = tokens.find((token) => line.includes(token.match));
          return (
            <motion.div
              key={`${index}-${line}`}
              className={`example-line ${active ? "example-line-hot" : ""}`}
              initial={reduce ? false : { opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <span className="mr-3 select-none text-muted/50">{index + 1}</span>
              <span>{line || " "}</span>
              {active ? (
                <span className="mt-1 block pl-8 text-xs text-muted">{active.explain}</span>
              ) : null}
            </motion.div>
          );
        })}
      </pre>
      {done ? (
        <button
          type="button"
          className="mt-4 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent"
          onClick={onStart}
        >
          I studied it — start typing
        </button>
      ) : (
        <button type="button" className="mt-4 text-sm text-accent" onClick={() => setShown(lines.length)}>
          Show all
        </button>
      )}
    </div>
  );
}
