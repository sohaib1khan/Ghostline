import { networkMessage } from "../offline.js";

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name) {
  const prefix = `${name}=`;
  const found = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : "";
}

function detailMessage(data) {
  if (!data) {
    return "Something went wrong";
  }
  if (typeof data.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join(" ");
  }
  return "Something went wrong";
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
  let data = null;
  if (text) {
    data = JSON.parse(text);
  }
  if (!response.ok) {
    const error = new Error(detailMessage(data));
    error.status = response.status;
    throw error;
  }
  return data;
}
