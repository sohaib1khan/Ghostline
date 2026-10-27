// DECISION: the runner is same-origin (allow-scripts allow-same-origin). A unique
// origin cannot load self-hosted Pyodide: module workers fail there, and
// connect-src 'self' does not include this host. Learner code runs in a worker
// with fetch, XHR, and importScripts replaced, so it cannot call the API.
// The parent stops waiting after 25 seconds; the frame kills the worker 3
// seconds after the code starts (longer for ghostwalk).

const PARENT_LIMIT_MS = 25000;

/**
 * @param {string} runtime browser_js | pyodide | ghostwalk | ghostwalk_js
 * @param {string} code
 * @param {{ level?: object, worldSource?: string, worldJsUrl?: string }} [extra]
 */
export function runInSandbox(runtime, code, extra = {}) {
  return new Promise((resolve) => {
    const frame = document.createElement("iframe");
    frame.hidden = true;
    frame.setAttribute("title", "Code sandbox");
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
    frame.src = "/sandbox/runner.html";
    let settled = false;

    function finish(result) {
      if (settled) {
        return;
      }
      settled = true;
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      frame.remove();
      resolve(result);
    }

    function onMessage(event) {
      if (event.source !== frame.contentWindow || event.origin !== window.location.origin) {
        return;
      }
      const data = event.data;
      if (!data || data.source !== "ghostline-sandbox") {
        return;
      }
      finish({
        output: typeof data.output === "string" ? data.output : "",
        error: data.error || null,
        result: data.result || null,
      });
    }

    const timer = window.setTimeout(
      () => finish({ output: "", error: "timeout", result: null }),
      PARENT_LIMIT_MS,
    );
    window.addEventListener("message", onMessage);
    frame.addEventListener("load", () => {
      frame.contentWindow?.postMessage(
        {
          source: "ghostline-parent",
          runtime,
          code,
          level: extra.level || null,
          worldSource: extra.worldSource || null,
          worldJsUrl: extra.worldJsUrl || null,
        },
        "*",
      );
    });
    document.body.appendChild(frame);
  });
}

let cachedWorld = null;

export async function loadGhostwalkWorld() {
  if (cachedWorld) {
    return cachedWorld;
  }
  const response = await fetch("/api/ghostwalk/world.py", { credentials: "include" });
  if (!response.ok) {
    const fallback = await fetch("/ghostwalk/world.py");
    if (!fallback.ok) {
      throw new Error("Could not load Ghostwalk world engine.");
    }
    cachedWorld = await fallback.text();
    return cachedWorld;
  }
  cachedWorld = await response.text();
  return cachedWorld;
}

function asGhostwalkResult(ran) {
  if (ran.error === "timeout") {
    return {
      ok: false,
      error: "That ran too long. Check for an infinite loop.",
      error_line: null,
      trace: [],
      actions: [],
    };
  }
  if (ran.result && typeof ran.result === "object") {
    return ran.result;
  }
  try {
    return JSON.parse(ran.output || "{}");
  } catch {
    return {
      ok: false,
      error: ran.output || ran.error || "Sandbox failed.",
      error_line: null,
      trace: [],
      actions: [],
    };
  }
}

export async function runGhostwalk(level, code, language = "python") {
  const { transpileGhostwalk } = await import("../../ghostwalk/languages.js");
  const prepared = transpileGhostwalk(language, code);
  if (prepared.runtime === "ghostwalk") {
    const worldSource = await loadGhostwalkWorld();
    const ran = await runInSandbox("ghostwalk", prepared.code, { level, worldSource });
    return asGhostwalkResult(ran);
  }
  const worldJs = await fetch("/ghostwalk/world.js").then((response) => {
    if (!response.ok) {
      throw new Error("Could not load Ghostwalk JS world engine.");
    }
    return response.text();
  });
  const ran = await runInSandbox("ghostwalk_js", prepared.code, {
    level,
    worldSource: worldJs,
  });
  return asGhostwalkResult(ran);
}
