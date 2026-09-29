// DECISION: the runner is same-origin (allow-scripts allow-same-origin). A unique
// origin cannot load self-hosted Pyodide: module workers fail there, and
// connect-src 'self' does not include this host. Learner code runs in a worker
// with fetch, XHR, and importScripts replaced, so it cannot call the API.
// The parent stops waiting after 25 seconds; the frame kills the worker 3
// seconds after the code starts.

const PARENT_LIMIT_MS = 25000;

export function runInSandbox(runtime, code) {
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
      });
    }

    const timer = window.setTimeout(
      () => finish({ output: "", error: "timeout" }),
      PARENT_LIMIT_MS,
    );
    window.addEventListener("message", onMessage);
    frame.addEventListener("load", () => {
      frame.contentWindow?.postMessage({ source: "ghostline-parent", runtime, code }, "*");
    });
    document.body.appendChild(frame);
  });
}
