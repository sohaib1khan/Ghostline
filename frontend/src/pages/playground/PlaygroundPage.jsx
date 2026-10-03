import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client.js";
import { readPrefs } from "../../prefs.js";
import { PYTHON_FLASK_STARTER } from "./flaskStarter.js";

function formatRemaining(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function formatDurationMinutes(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0));
  if (total <= 0) {
    return "a short while";
  }
  if (total < 60) {
    return `${total} minute${total === 1 ? "" : "s"}`;
  }
  const hours = Math.floor(total / 60);
  const rem = total % 60;
  if (rem === 0) {
    return `${hours} hour${hours === 1 ? "" : "s"}`;
  }
  return `${hours}h ${rem}m`;
}

function formatExtendLabel(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0));
  if (total < 60) {
    return `Extend ${total}m`;
  }
  const hours = Math.floor(total / 60);
  const rem = total % 60;
  if (rem === 0) {
    return `Extend ${hours}h`;
  }
  return `Extend ${hours}h ${rem}m`;
}

const DEFAULT_TTL_MINUTES = 720;
const DEFAULT_FILE = "templates/python-hello/main.py";
const WEB_PREVIEW = "templates/web-hello/index.html";

function langFromPath(filePath) {
  const lower = (filePath || "").toLowerCase();
  if (lower.includes("/python-flask/")) {
    return "flask";
  }
  if (lower.endsWith(".py")) {
    return "python";
  }
  if (lower.endsWith(".js") || lower.endsWith(".mjs")) {
    return "javascript";
  }
  if (lower.endsWith(".sh") || lower.endsWith(".bash")) {
    return "bash";
  }
  if (lower.endsWith(".cs")) {
    return "csharp";
  }
  if (lower.endsWith(".java")) {
    return "java";
  }
  if (lower.endsWith(".html") || lower.endsWith(".htm") || lower.endsWith(".css")) {
    return "web";
  }
  return "file";
}

const LANGS = [
  {
    id: "python",
    label: "Python",
    tip: "templates/python-hello",
    file: "templates/python-hello/main.py",
    starter: 'print("hello from the playground")\n',
    view: "editor",
    color: "#3776ab",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <path
          fill="currentColor"
          d="M12 2C7.8 2 7.5 4 7.5 4v2.5h5v.8H5.2S3 7.2 3 11.8s1.9 4.5 1.9 4.5h2.4v-2.2s-.1-2.6 2.6-2.6H15s2.5.1 2.5-2.4V4.2S17.8 2 12 2zm-2.2 1.4a.9.9 0 1 1 0 1.8.9.9 0 0 1 0-1.8z"
        />
        <path
          fill="currentColor"
          opacity="0.72"
          d="M12 22c4.2 0 4.5-2 4.5-2v-2.5h-5v-.8h7.3S21 16.8 21 12.2s-1.9-4.5-1.9-4.5h-2.4v2.2s.1 2.6-2.6 2.6H9s-2.5-.1-2.5 2.4v4.7S6.2 22 12 22zm2.2-1.4a.9.9 0 1 1 0-1.8.9.9 0 0 1 0 1.8z"
        />
      </svg>
    ),
  },
  {
    id: "flask",
    label: "Flask",
    tip: "templates/python-flask — install flask first",
    file: "templates/python-flask/app.py",
    starter: PYTHON_FLASK_STARTER,
    view: "editor",
    color: "#0f766e",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="currentColor" opacity="0.16" />
        <path
          fill="currentColor"
          d="M7 4h10v2H7V4zm1 4h8l-1 12H9L8 8zm2 2v8h1v-8H10zm3 0v8h1v-8h-1z"
        />
      </svg>
    ),
  },
  {
    id: "javascript",
    label: "JavaScript",
    tip: "templates/javascript-hello",
    file: "templates/javascript-hello/main.js",
    starter: 'console.log("hello from the playground");\n',
    view: "editor",
    color: "#c4a035",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="currentColor" opacity="0.18" />
        <path
          fill="currentColor"
          d="M10.2 17.6c0 1.5-.9 2.4-2.4 2.4-1.1 0-1.9-.5-2.3-1.3l1.3-.8c.2.4.5.6.9.6.5 0 .8-.3.8-1.1V12h1.7v5.6zm4.8 2.4c-1.4 0-2.3-.7-2.7-1.6l1.3-.8c.3.5.7.8 1.3.8.6 0 1-.3 1-.7 0-.5-.4-.7-1.1-1l-.4-.2c-1.1-.5-1.9-1.1-1.9-2.4 0-1.2.9-2.1 2.3-2.1 1 0 1.7.3 2.2 1.2l-1.2.8c-.3-.4-.6-.6-1-.6-.4 0-.7.3-.7.6 0 .4.3.6 1 .9l.4.2c1.3.6 2 1.2 2 2.5 0 1.4-1.1 2.2-2.5 2.2z"
        />
      </svg>
    ),
  },
  {
    id: "bash",
    label: "Bash",
    tip: "templates/bash-hello",
    file: "templates/bash-hello/main.sh",
    starter: '#!/usr/bin/env bash\necho "hello from the playground"\n',
    view: "editor",
    color: "#5f8f7e",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="currentColor" opacity="0.16" />
        <path
          fill="currentColor"
          d="M5.5 8.2 10 12l-4.5 3.8-.9-1.1L7.8 12 4.6 9.3l.9-1.1zm6.2 7.3h7.2v1.4h-7.2V15.5z"
        />
      </svg>
    ),
  },
  {
    id: "csharp",
    label: "C#",
    tip: "templates/csharp-hello — Mono compile + run",
    file: "templates/csharp-hello/Program.cs",
    starter:
      'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        Console.WriteLine("hello from the playground");\n    }\n}\n',
    view: "editor",
    color: "#6b7bb8",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="currentColor" opacity="0.18" />
        <text
          x="12"
          y="16"
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize="9"
          fontWeight="700"
          fill="currentColor"
        >
          C#
        </text>
      </svg>
    ),
  },
  {
    id: "java",
    label: "Java",
    tip: "templates/java-hello — javac + java",
    file: "templates/java-hello/Main.java",
    starter:
      'public class Main {\n    public static void main(String[] args) {\n        System.out.println("hello from the playground");\n    }\n}\n',
    view: "editor",
    color: "#c4785a",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="currentColor" opacity="0.18" />
        <text
          x="12"
          y="16"
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize="8"
          fontWeight="700"
          fill="currentColor"
        >
          Java
        </text>
      </svg>
    ),
  },
  {
    id: "web",
    label: "Web",
    tip: "templates/web-hello — preview in Browser",
    file: WEB_PREVIEW,
    starter: "",
    view: "browser",
    color: "#c2410c",
    mark: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        <rect width="24" height="24" rx="4" fill="currentColor" opacity="0.16" />
        <path
          fill="currentColor"
          d="M4.5 4.5h15l-1.4 15.2L12 21.5l-6.1-1.8L4.5 4.5zm3.2 4.2.4 4.4h5.6l-.2 2.1-2.5.7-2.5-.7-.2-1.7H6.7l.3 3.2L12 18l5-1.4.7-7.9H7.7z"
        />
      </svg>
    ),
  },
];

function canRunPath(filePath) {
  const lower = (filePath || "").toLowerCase();
  return lower.endsWith(".py") || lower.endsWith(".js") || lower.endsWith(".mjs") || lower.endsWith(".sh") || lower.endsWith(".bash");
}

function isHtmlPath(filePath) {
  const lower = (filePath || "").toLowerCase();
  return lower.endsWith(".html") || lower.endsWith(".htm");
}

/** Show the last 1–2 path segments; full path goes on title/aria-label. */
function displayPath(filePath) {
  const parts = (filePath || "").split("/").filter(Boolean);
  if (parts.length <= 2) {
    return parts.join("/") || filePath;
  }
  return parts.slice(-2).join("/");
}

function FileMark({ kind }) {
  const lang = LANGS.find((item) => item.id === kind);
  if (!lang) {
    return (
      <span className="inline-flex h-5 w-5 items-center justify-center rounded text-[10px] text-muted">
        ·
      </span>
    );
  }
  return (
    <span className="inline-flex text-[color:var(--lang)]" style={{ "--lang": lang.color }}>
      {lang.mark}
    </span>
  );
}

function SprinkleField({ reduce }) {
  const dots = [
    { left: "8%", top: "18%", delay: "0s", size: 5 },
    { left: "22%", top: "62%", delay: "0.4s", size: 3 },
    { left: "41%", top: "28%", delay: "1.1s", size: 4 },
    { left: "58%", top: "70%", delay: "0.2s", size: 3 },
    { left: "73%", top: "22%", delay: "0.8s", size: 5 },
    { left: "86%", top: "48%", delay: "1.4s", size: 3 },
    { left: "94%", top: "14%", delay: "0.6s", size: 4 },
  ];
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {dots.map((dot) => (
        <span
          key={`${dot.left}-${dot.top}`}
          className={reduce ? "playground-sprinkle" : "playground-sprinkle playground-sprinkle-float"}
          style={{
            left: dot.left,
            top: dot.top,
            width: dot.size,
            height: dot.size,
            animationDelay: reduce ? undefined : dot.delay,
          }}
        />
      ))}
    </div>
  );
}

export default function PlaygroundPage() {
  const systemReduce = useReducedMotion();
  const [prefs] = useState(readPrefs);
  const reduce = Boolean(systemReduce) || prefs.reduceMotion;
  const [limits, setLimits] = useState(null);
  const [session, setSession] = useState(null);
  const [entries, setEntries] = useState([]);
  const [path, setPath] = useState(DEFAULT_FILE);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [output, setOutput] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [running, setRunning] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [newFile, setNewFile] = useState("");
  const [newFolder, setNewFolder] = useState("");
  const [burstKey, setBurstKey] = useState(0);
  const [command, setCommand] = useState("");
  const [deskView, setDeskView] = useState("editor");
  const [previewPath, setPreviewPath] = useState(WEB_PREVIEW);
  const [previewKey, setPreviewKey] = useState(0);
  const [pkgEco, setPkgEco] = useState("pip");
  const [pkgNames, setPkgNames] = useState("");
  const [pkgLog, setPkgLog] = useState("");
  const [installing, setInstalling] = useState(false);

  const files = useMemo(
    () => entries.filter((item) => item.type === "file").map((item) => item.path).sort(),
    [entries],
  );
  const folders = useMemo(
    () => entries.filter((item) => item.type === "dir").map((item) => item.path).sort(),
    [entries],
  );
  const activeLang = langFromPath(path);
  const lifetimeMinutes = Math.max(
    DEFAULT_TTL_MINUTES,
    Number(limits?.ttl_default_minutes) || DEFAULT_TTL_MINUTES,
  );
  const lifetimeLabel = formatDurationMinutes(lifetimeMinutes);
  const lifetimeSeconds = lifetimeMinutes * 60;
  const timerPct = session
    ? Math.min(100, Math.round((remaining / Math.max(1, session.ttl_seconds || lifetimeSeconds)) * 100))
    : 0;

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      try {
        const status = await api("/api/playground/status");
        if (cancelled) {
          return;
        }
        setLimits(status);
        if (!status.enabled) {
          setMessage("Playground is turned off on this server.");
          return;
        }
        const body = await api("/api/playground/session");
        if (cancelled) {
          return;
        }
        if (body.session) {
          setSession(body.session);
          setRemaining(body.session.remaining_seconds || 0);
          await refreshTree();
          await openFile(DEFAULT_FILE);
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(error.message);
        }
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!session) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setRemaining((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session?.session_id]);

  useEffect(() => {
    if (session && remaining === 0) {
      setMessage(
        "Session ended — the container was destroyed. Start again for a fresh workspace.",
      );
      setSession(null);
      setEntries([]);
      setContent("");
    }
  }, [remaining, session]);

  async function refreshTree() {
    const body = await api("/api/playground/fs/tree");
    setEntries(body.entries || []);
  }

  async function openFile(nextPath) {
    const body = await api(`/api/playground/fs/file?path=${encodeURIComponent(nextPath)}`);
    setPath(nextPath);
    setContent(body.content || "");
    setDirty(false);
    if (isHtmlPath(nextPath)) {
      setPreviewPath(nextPath);
    }
  }

  async function openLang(langId) {
    if (!session || pending) {
      return;
    }
    const lang = LANGS.find((item) => item.id === langId);
    if (!lang) {
      return;
    }
    setPending(true);
    setMessage("");
    try {
      let writeStarter = Boolean(lang.starter) && !files.includes(lang.file);
      if (langId === "flask" && files.includes(lang.file)) {
        try {
          const existing = await api(
            `/api/playground/fs/file?path=${encodeURIComponent(lang.file)}`,
          );
          if (/\bapp\.run\s*\(/.test(existing.content || "")) {
            writeStarter = true;
            setMessage(
              "Reset flask template — app.run() is not supported (use test_client).",
            );
          }
        } catch {
          writeStarter = true;
        }
      }
      if (writeStarter && lang.starter) {
        await api("/api/playground/fs/file", {
          method: "PUT",
          body: { path: lang.file, content: lang.starter },
        });
        await refreshTree();
      }
      await openFile(lang.file);
      if (lang.view === "browser" || isHtmlPath(lang.file)) {
        setPreviewPath(lang.file);
        setPreviewKey((value) => value + 1);
        setDeskView("browser");
      } else {
        setDeskView("editor");
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function startSession() {
    setPending(true);
    setMessage("");
    try {
      const body = await api("/api/playground/start", {
        method: "POST",
        body: {},
      });
      setSession(body);
      setRemaining(body.remaining_seconds || body.ttl_seconds || lifetimeSeconds);
      setBurstKey((value) => value + 1);
      await refreshTree();
      await openFile(DEFAULT_FILE);
      setMessage(
        body.resumed
          ? `Resumed your open session. Container still destroys in ${formatRemaining(body.remaining_seconds || body.ttl_seconds)} unless you extend.`
          : `Session started. This container will be destroyed in ${lifetimeLabel} unless you extend it.`,
      );
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function extendSession() {
    setPending(true);
    setMessage("");
    try {
      const body = await api("/api/playground/session/ttl", {
        method: "PATCH",
        body: {},
      });
      setSession((current) => ({ ...(current || {}), ...body }));
      setRemaining(body.remaining_seconds || lifetimeSeconds);
      setMessage(
        `Extended — container will now be destroyed in ${lifetimeLabel} from now.`,
      );
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function stopSession() {
    setPending(true);
    setMessage("");
    try {
      await api("/api/playground/stop", { method: "POST" });
      setSession(null);
      setEntries([]);
      setContent("");
      setOutput("");
      setRemaining(0);
      setDeskView("editor");
      setPkgLog("");
      setMessage("Session stopped. Worker and files are gone.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function refreshPreview() {
    if (dirty && isHtmlPath(path)) {
      setPending(true);
      try {
        await api("/api/playground/fs/file", {
          method: "PUT",
          body: { path, content },
        });
        setDirty(false);
        await refreshTree();
      } catch (error) {
        setMessage(error.message);
        setPending(false);
        return;
      }
      setPending(false);
    }
    const next = isHtmlPath(path)
      ? path
      : files.includes(WEB_PREVIEW)
        ? WEB_PREVIEW
        : previewPath || WEB_PREVIEW;
    setPreviewPath(next);
    setPreviewKey((value) => value + 1);
    setDeskView("browser");
    if (isHtmlPath(next) && path !== next && files.includes(next)) {
      try {
        await openFile(next);
      } catch {
        // Preview can still load via iframe even if editor sync fails.
      }
    }
  }

  async function installPackages() {
    const names = pkgNames
      .split(/[,\s]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (!names.length) {
      setMessage("Enter at least one package name.");
      return;
    }
    setInstalling(true);
    setPending(true);
    setMessage("");
    setPkgLog("Downloading on the server, then installing offline inside your box…");
    try {
      const body = await api("/api/playground/packages", {
        method: "POST",
        body: { ecosystem: pkgEco, packages: names },
      });
      setPkgLog(body.output || `Installed into ${body.target}`);
      setMessage(
        body.hint ||
          `Installed ${names.join(", ")}. The worker still has no network — nothing can leave the box.`,
      );
      setBurstKey((value) => value + 1);
      await refreshTree();
    } catch (error) {
      setPkgLog(error.message);
      setMessage(error.message);
    } finally {
      setInstalling(false);
      setPending(false);
    }
  }

  async function saveFile() {
    setPending(true);
    setMessage("");
    try {
      await api("/api/playground/fs/file", {
        method: "PUT",
        body: { path, content },
      });
      setDirty(false);
      await refreshTree();
      setMessage(`Saved ${path}`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function runFile() {
    if (!canRunPath(path)) {
      setMessage("Open a .py, .js, or .sh file to Run — or type a bash command below.");
      return;
    }
    setPending(true);
    setRunning(true);
    setMessage("");
    try {
      if (dirty) {
        await api("/api/playground/fs/file", {
          method: "PUT",
          body: { path, content },
        });
        setDirty(false);
      }
      const body = await api("/api/playground/run", {
        method: "POST",
        body: { path },
      });
      setOutput(
        `$ ${((body.argv || []).join(" ") || path)}\n${body.output || ""}\n(exit ${body.exit_code})`,
      );
      setBurstKey((value) => value + 1);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
      setRunning(false);
    }
  }

  async function runShell(event) {
    event?.preventDefault?.();
    const line = command.trim();
    if (!line || pending) {
      return;
    }
    setPending(true);
    setRunning(true);
    setMessage("");
    try {
      const body = await api("/api/playground/run", {
        method: "POST",
        body: { shell: line },
      });
      const chunk = `$ ${line}\n${body.output || ""}\n(exit ${body.exit_code})`;
      setOutput((prev) => (prev ? `${prev}\n\n${chunk}` : chunk));
      setCommand("");
      setBurstKey((value) => value + 1);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
      setRunning(false);
    }
  }

  async function createFile() {
    const next = newFile.trim().replace(/^\/+/, "");
    if (!next) {
      return;
    }
    setPending(true);
    try {
      await api("/api/playground/fs/file", {
        method: "PUT",
        body: { path: next, content: "" },
      });
      setNewFile("");
      await refreshTree();
      await openFile(next);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function createFolder() {
    const next = newFolder.trim().replace(/^\/+/, "");
    if (!next) {
      return;
    }
    setPending(true);
    try {
      await api("/api/playground/fs/mkdir", {
        method: "POST",
        body: { path: next },
      });
      setNewFolder("");
      await refreshTree();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  async function removePath(target) {
    if (!window.confirm(`Delete ${target}?`)) {
      return;
    }
    setPending(true);
    try {
      await api(`/api/playground/fs/path?path=${encodeURIComponent(target)}`, {
        method: "DELETE",
      });
      if (path === target) {
        setPath(DEFAULT_FILE);
        setContent("");
      }
      await refreshTree();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  const disabled = !limits?.enabled;
  const rise = reduce
    ? {}
    : {
        initial: { opacity: 0, y: 10 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.45, ease: "easeOut" },
      };

  return (
    <section className="playground-shell relative overflow-hidden rounded-2xl bg-surface p-4 shadow-[var(--shadow)] sm:p-6">
      <SprinkleField reduce={reduce} />

      <div className="relative">
        <motion.p
          className="font-mono text-xs uppercase tracking-[0.2em] text-accent"
          {...rise}
        >
          Playground
        </motion.p>
        <motion.h1
          className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl"
          {...rise}
          transition={{ ...(rise.transition || {}), delay: reduce ? 0 : 0.06 }}
        >
          Try code in a throwaway box
        </motion.h1>
        <motion.p
          className="mt-2 max-w-2xl text-sm text-muted"
          {...rise}
          transition={{ ...(rise.transition || {}), delay: reduce ? 0 : 0.12 }}
        >
          A worker starts for you alone. The box itself has no network out — packages are
          fetched by the server and installed offline. Your container and files are destroyed
          after {lifetimeLabel} unless you extend the session.
        </motion.p>

        <ul className="mt-5 flex flex-wrap gap-2">
          {LANGS.map((lang, index) => (
            <motion.li
              key={lang.id}
              initial={reduce ? false : { opacity: 0, y: 8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={reduce ? { duration: 0 } : { delay: 0.15 + index * 0.08, duration: 0.4 }}
            >
              <button
                type="button"
                disabled={!session || pending}
                onClick={() => openLang(lang.id)}
                title={session ? lang.tip : "Start a session first"}
                className={`playground-lang-chip inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60 ${
                  activeLang === lang.id && session ? "playground-lang-chip-hot" : ""
                }`}
                style={{ "--lang": lang.color }}
              >
                <span className="text-[color:var(--lang)]">{lang.mark}</span>
                <span>{lang.label}</span>
              </button>
            </motion.li>
          ))}
        </ul>

        <div className="mt-6 flex flex-wrap items-end gap-3">
          {!session ? (
            <button
              type="button"
              disabled={disabled || pending}
              onClick={startSession}
              className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-50"
            >
              {pending ? "Starting…" : "Start session"}
            </button>
          ) : (
            <>
              <button
                type="button"
                disabled={pending}
                onClick={extendSession}
                className="rounded-xl border border-muted/30 px-4 py-2 text-sm disabled:opacity-50"
              >
                {formatExtendLabel(lifetimeMinutes)}
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={stopSession}
                className="rounded-xl border border-error/40 px-4 py-2 text-sm text-error disabled:opacity-50"
              >
                End session
              </button>
              <div className="min-w-[11rem]">
                <p className="font-mono text-sm text-muted">
                  Destroys in {formatRemaining(remaining)}
                  {limits?.memory_mb ? ` · ${limits.memory_mb}MB` : ""}
                </p>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted/20">
                  <div
                    className="playground-timer-bar h-full rounded-full bg-accent"
                    style={{ width: `${timerPct}%` }}
                  />
                </div>
              </div>
            </>
          )}
        </div>
        {limits ? (
          <p className="mt-2 text-xs text-muted">
            Sessions last {lifetimeLabel}. Extend anytime to reset the clock. One session
            per account.
          </p>
        ) : null}
        {message ? (
          <motion.p
            key={message}
            className="mt-3 text-sm text-muted"
            role="status"
            initial={reduce ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {message}
          </motion.p>
        ) : null}
      </div>

      {session ? (
        <motion.div
          key={`desk-${session.session_id || "active"}`}
          className="relative mt-6 grid gap-4 lg:grid-cols-[minmax(16rem,20rem)_minmax(0,1fr)]"
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {!reduce ? (
            <span key={burstKey} className="playground-burst" aria-hidden="true" />
          ) : null}

          <aside className="playground-panel rounded-xl border border-muted/20 p-3">
            <p className="text-xs font-medium uppercase tracking-wider text-muted">Files</p>
            <ul className="mt-2 flex max-h-64 flex-col gap-1 overflow-auto text-sm">
              {folders.map((folder, index) => (
                <motion.li
                  key={`d-${folder}`}
                  className="flex items-center justify-between gap-2 text-muted"
                  title={folder}
                  initial={reduce ? false : { opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: reduce ? 0 : index * 0.03 }}
                >
                  <span className="flex min-w-0 items-center gap-2 font-mono">
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center text-muted" aria-hidden="true">
                      <svg viewBox="0 0 24 24" className="h-4 w-4">
                        <path
                          fill="currentColor"
                          d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2h7.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-9z"
                          opacity="0.75"
                        />
                      </svg>
                    </span>
                    <span className="truncate" title={`${folder}/`}>
                      {displayPath(folder)}/
                    </span>
                  </span>
                  <button
                    type="button"
                    className="shrink-0 text-xs text-error"
                    title={`Delete ${folder}`}
                    onClick={() => removePath(folder)}
                  >
                    Del
                  </button>
                </motion.li>
              ))}
              {files.map((file, index) => (
                <motion.li
                  key={file}
                  className="flex items-center justify-between gap-2"
                  title={file}
                  initial={reduce ? false : { opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: reduce ? 0 : 0.05 + index * 0.03 }}
                >
                  <button
                    type="button"
                    className={`flex min-w-0 items-center gap-2 text-left font-mono ${
                      file === path ? "text-accent" : "text-text"
                    }`}
                    title={file}
                    aria-label={file}
                    onClick={() => {
                      setDeskView("editor");
                      openFile(file);
                    }}
                  >
                    <FileMark kind={langFromPath(file)} />
                    <span className="truncate">{displayPath(file)}</span>
                  </button>
                  <button
                    type="button"
                    className="shrink-0 text-xs text-error"
                    title={`Delete ${file}`}
                    onClick={() => removePath(file)}
                  >
                    Del
                  </button>
                </motion.li>
              ))}
            </ul>
            <div className="mt-3 flex flex-col gap-2">
              <input
                value={newFile}
                onChange={(event) => setNewFile(event.target.value)}
                placeholder="new file.py"
                className="rounded-lg border border-muted/30 bg-bg px-2 py-1 font-mono text-xs"
              />
              <button type="button" className="text-left text-xs text-accent" onClick={createFile}>
                Add file
              </button>
              <input
                value={newFolder}
                onChange={(event) => setNewFolder(event.target.value)}
                placeholder="folder"
                className="rounded-lg border border-muted/30 bg-bg px-2 py-1 font-mono text-xs"
              />
              <button type="button" className="text-left text-xs text-accent" onClick={createFolder}>
                Add folder
              </button>
            </div>
            <div className="mt-4 border-t border-muted/15 pt-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted">Packages</p>
              <p className="mt-1 text-[11px] leading-snug text-muted">
                Server downloads; worker installs offline. The box never gets network.
              </p>
              <select
                value={pkgEco}
                onChange={(event) => setPkgEco(event.target.value)}
                className="mt-2 w-full rounded-lg border border-muted/30 bg-bg px-2 py-1 text-xs"
              >
                <option value="pip">pip (Python)</option>
                <option value="npm">npm (Node)</option>
              </select>
              <input
                value={pkgNames}
                onChange={(event) => setPkgNames(event.target.value)}
                placeholder={pkgEco === "pip" ? "requests flask" : "lodash chalk"}
                className="mt-2 w-full rounded-lg border border-muted/30 bg-bg px-2 py-1 font-mono text-xs"
              />
              <button
                type="button"
                disabled={pending || installing}
                onClick={installPackages}
                className="mt-2 text-left text-xs text-accent disabled:opacity-50"
              >
                {installing ? "Installing…" : "Install"}
              </button>
              {pkgLog ? (
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-muted">
                  {pkgLog}
                </pre>
              ) : null}
            </div>
          </aside>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex gap-1 rounded-xl border border-muted/20 p-0.5">
                <button
                  type="button"
                  onClick={() => setDeskView("editor")}
                  className={`rounded-lg px-3 py-1 text-sm ${
                    deskView === "editor" ? "bg-accent text-on-accent" : "text-muted"
                  }`}
                >
                  Editor
                </button>
                <button
                  type="button"
                  onClick={refreshPreview}
                  className={`rounded-lg px-3 py-1 text-sm ${
                    deskView === "browser" ? "bg-accent text-on-accent" : "text-muted"
                  }`}
                >
                  Browser
                </button>
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <FileMark kind={activeLang} />
                <p className="truncate font-mono text-sm text-muted">
                  {deskView === "browser" ? previewPath : path}
                </p>
              </div>
              {dirty && deskView === "editor" ? (
                <span className="rounded-full bg-muted/15 px-2 py-0.5 text-xs text-muted">
                  unsaved
                </span>
              ) : null}
              <div className="ml-auto flex flex-wrap gap-2">
                {deskView === "editor" ? (
                  <>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={saveFile}
                      className="rounded-xl border border-muted/30 px-3 py-1.5 text-sm disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      disabled={pending || !canRunPath(path)}
                      onClick={runFile}
                      className={`rounded-xl bg-accent px-3 py-1.5 text-sm font-medium text-on-accent disabled:opacity-50 ${
                        running && !reduce ? "playground-run-pulse" : ""
                      }`}
                    >
                      {running ? "Running…" : "Run"}
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={refreshPreview}
                    className="rounded-xl border border-muted/30 px-3 py-1.5 text-sm disabled:opacity-50"
                  >
                    Refresh
                  </button>
                )}
              </div>
            </div>

            {deskView === "browser" ? (
              <div className="playground-browser mt-3 overflow-hidden rounded-xl border border-muted/20 bg-bg">
                <div className="flex items-center gap-2 border-b border-muted/20 px-3 py-2">
                  <span className="h-2 w-2 rounded-full bg-muted/40" aria-hidden="true" />
                  <span className="h-2 w-2 rounded-full bg-muted/40" aria-hidden="true" />
                  <span className="h-2 w-2 rounded-full bg-muted/40" aria-hidden="true" />
                  <p className="truncate font-mono text-xs text-muted">
                    preview://{previewPath}
                  </p>
                </div>
                <iframe
                  key={`${previewPath}-${previewKey}`}
                  title="Playground browser"
                  src={`/api/playground/preview/${previewPath}?v=${previewKey}`}
                  sandbox="allow-scripts"
                  className="h-[28rem] w-full bg-white"
                  referrerPolicy="no-referrer"
                />
              </div>
            ) : (
              <>
            <textarea
              value={content}
              onChange={(event) => {
                setContent(event.target.value);
                setDirty(true);
              }}
              onKeyDown={(event) => {
                const area = event.currentTarget;
                const start = area.selectionStart;
                const end = area.selectionEnd;
                if (event.key === "Tab") {
                  event.preventDefault();
                  const next = `${content.slice(0, start)}  ${content.slice(end)}`;
                  setContent(next);
                  setDirty(true);
                  queueMicrotask(() => {
                    area.selectionStart = area.selectionEnd = start + 2;
                  });
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const lineStart = content.lastIndexOf("\n", start - 1) + 1;
                  const indent = /^[ \t]*/.exec(content.slice(lineStart, start))?.[0] || "";
                  const insert = `\n${indent}`;
                  const next = `${content.slice(0, start)}${insert}${content.slice(end)}`;
                  setContent(next);
                  setDirty(true);
                  queueMicrotask(() => {
                    area.selectionStart = area.selectionEnd = start + insert.length;
                  });
                }
              }}
              spellCheck={false}
              className="playground-editor mt-3 h-72 w-full rounded-xl border border-muted/20 bg-bg p-3 font-mono text-sm leading-relaxed"
            />
            <div className="playground-terminal mt-3 overflow-hidden rounded-xl border border-muted/20 bg-bg">
              <pre className="max-h-48 overflow-auto p-3 font-mono text-xs text-muted whitespace-pre-wrap">
                {output || "Output shows here after Run or a bash command."}
              </pre>
              <form
                className="flex items-center gap-2 border-t border-muted/20 px-3 py-2"
                onSubmit={runShell}
              >
                <span className="font-mono text-sm text-accent" aria-hidden="true">
                  $
                </span>
                <input
                  value={command}
                  onChange={(event) => setCommand(event.target.value)}
                  disabled={pending}
                  placeholder="ls · echo hi · bash command"
                  aria-label="Bash command"
                  className="min-w-0 flex-1 bg-transparent font-mono text-sm outline-none placeholder:text-muted/60"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="submit"
                  disabled={pending || !command.trim()}
                  className="shrink-0 text-xs text-accent disabled:opacity-40"
                >
                  Enter
                </button>
              </form>
            </div>
              </>
            )}
          </div>
        </motion.div>
      ) : null}
    </section>
  );
}
