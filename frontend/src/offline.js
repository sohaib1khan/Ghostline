export const OFFLINE_NOTICE =
  "You're offline. You can keep reading a lesson you already opened. Sending an answer needs a connection.";

export function networkMessage(method) {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return OFFLINE_NOTICE;
  }
  if (method && method.toUpperCase() !== "GET") {
    return "The API is unreachable. Nothing was sent.";
  }
  return "The API is unreachable";
}
