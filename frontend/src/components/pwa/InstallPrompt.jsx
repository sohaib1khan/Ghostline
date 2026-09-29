import { useEffect, useRef, useState } from "react";

const DISMISS_KEY = "ghostline-install-dismissed";

function installed() {
  return (
    window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true
  );
}

function iosSafari() {
  const agent = navigator.userAgent;
  const apple =
    /iphone|ipad|ipod/i.test(agent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return apple && /safari/i.test(agent) && !/crios|fxios|edgios/i.test(agent);
}

export default function InstallPrompt() {
  const deferred = useRef(null);
  const [mode, setMode] = useState(null);

  useEffect(() => {
    if (localStorage.getItem(DISMISS_KEY) === "1" || installed()) {
      return undefined;
    }
    function onPrompt(event) {
      event.preventDefault();
      deferred.current = event;
      setMode("native");
    }
    window.addEventListener("beforeinstallprompt", onPrompt);
    if (iosSafari()) {
      setMode((current) => current || "ios");
    }
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  function dismiss() {
    localStorage.setItem(DISMISS_KEY, "1");
    deferred.current = null;
    setMode(null);
  }

  async function install() {
    const event = deferred.current;
    if (!event) {
      return;
    }
    await event.prompt();
    deferred.current = null;
    setMode(null);
  }

  if (!mode) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-muted/30 bg-surface px-3 py-2 text-sm">
      <p>
        {mode === "ios"
          ? "To install Ghostline, open Share and choose Add to Home Screen."
          : "Install Ghostline on this device."}
      </p>
      <div className="flex gap-4">
        {mode === "native" ? (
          <button type="button" className="min-h-10 text-accent" onClick={install}>
            Install
          </button>
        ) : null}
        <button type="button" className="min-h-10 text-muted" onClick={dismiss}>
          Not now
        </button>
      </div>
    </div>
  );
}
