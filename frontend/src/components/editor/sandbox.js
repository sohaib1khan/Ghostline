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
 * @param {{ level?: object, worldSource?: string, skinsSource?: string, language?: string, worldJsUrl?: string }} [extra]
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
          language: extra.language || "python",
          worldSource: extra.worldSource || null,
          skinsSource: extra.skinsSource || null,
          worldJsUrl: extra.worldJsUrl || null,
        },
        "*",
      );
    });
    document.body.appendChild(frame);
  });
}

const runtimeCache = { world: null, skins: null, worldJs: null };

async function fetchRuntimeText(url, fallbackUrl) {
  const response = await fetch(url, { credentials: "include" });
  if (response.ok) {
    return response.text();
  }
  if (fallbackUrl) {
    const fallback = await fetch(fallbackUrl);
    if (fallback.ok) {
      return fallback.text();
    }
  }
  throw new Error(`Could not load ${url}`);
}

export async function loadGhostwalkWorld() {
  if (runtimeCache.world) {
    return runtimeCache.world;
  }
  runtimeCache.world = await fetchRuntimeText(
    "/api/ghostwalk/runtime/world.py",
    "/ghostwalk/world.py",
  );
  return runtimeCache.world;
}

export async function loadGhostwalkSkins() {
  if (runtimeCache.skins) {
    return runtimeCache.skins;
  }
  runtimeCache.skins = await fetchRuntimeText("/api/ghostwalk/runtime/skins.py");
  return runtimeCache.skins;
}

async function loadGhostwalkWorldJs() {
  if (runtimeCache.worldJs) {
    return runtimeCache.worldJs;
  }
  const response = await fetch("/ghostwalk/world.js");
  if (!response.ok) {
    throw new Error("Could not load Ghostwalk JS world engine.");
  }
  runtimeCache.worldJs = await response.text();
  return runtimeCache.worldJs;
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
  const { ghostwalkRuntime } = await import("../../ghostwalk/languages.js");
  const lang = String(language || "python").toLowerCase();
  const runtime = ghostwalkRuntime(lang);
  if (runtime === "ghostwalk_js") {
    const worldJs = await loadGhostwalkWorldJs();
    const ran = await runInSandbox("ghostwalk_js", code, {
      level,
      language: lang,
      worldSource: worldJs,
    });
    return asGhostwalkResult(ran);
  }
  const [worldSource, skinsSource] = await Promise.all([
    loadGhostwalkWorld(),
    lang === "python" ? Promise.resolve("") : loadGhostwalkSkins(),
  ]);
  const ran = await runInSandbox("ghostwalk", code, {
    level,
    language: lang,
    worldSource,
    skinsSource,
  });
  return asGhostwalkResult(ran);
}
