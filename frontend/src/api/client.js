import { networkMessage } from "../offline.js";

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name) {
  const prefix = `${name}=`;
  const found = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : "";
}

function detailMessage(data, status, text) {
  if (data) {
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join(" ");
    }
  }
  if (status === 502 || status === 503 || status === 504) {
    return "The playground service is unreachable. Try again in a moment.";
  }
  if (status === 0) {
    return networkMessage("GET");
  }
  const trimmed = (text || "").trim();
  if (trimmed.startsWith("<") || trimmed.toLowerCase().startsWith("<!doctype")) {
    return "The server returned a page instead of data. Refresh and try again.";
  }
  if (trimmed && trimmed.length < 180) {
    return trimmed;
  }
  return "Something went wrong";
}

function parseBody(text) {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = new Headers();
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (UNSAFE.has(method.toUpperCase())) {
    headers.set("X-CSRF-Token", readCookie("ghostline_csrf"));
  }
  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // DECISION: a failed send is not queued. The learner retries when online.
    const error = new Error(networkMessage(method));
    error.status = 0;
    throw error;
  }
  const text = await response.text();
  const data = parseBody(text);
  if (!response.ok) {
    const error = new Error(detailMessage(data, response.status, text));
    error.status = response.status;
    throw error;
  }
  if (text && data === null) {
    const error = new Error(detailMessage(null, response.status, text));
    error.status = response.status || 502;
    throw error;
  }
  return data;
}
