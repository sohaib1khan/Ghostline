import { useEffect, useState } from "react";

export default function SimulatedTerminal({ text, reduceMotion }) {
  const lines = String(text || "").split("\n");
  const [shown, setShown] = useState(reduceMotion ? lines.length : 0);

  useEffect(() => {
    if (reduceMotion) {
      return undefined;
    }
    if (shown >= lines.length) {
      return undefined;
    }
    const timer = window.setTimeout(() => setShown((count) => count + 1), 160);
    return () => window.clearTimeout(timer);
  }, [reduceMotion, shown, lines.length]);

  const visible = reduceMotion ? lines : lines.slice(0, shown);
  return (
    <pre className="mt-3 overflow-x-auto rounded-xl bg-bg p-3 font-mono text-sm text-text">
      {visible.join("\n")}
    </pre>
  );
}
