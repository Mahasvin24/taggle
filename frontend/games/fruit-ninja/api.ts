export const base = "/api/games/fruit-ninja";
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(base + path, {
    signal: AbortSignal.timeout(8000),
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `Save failed (${response.status}).`;
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      /* Keep HTTP error. */
    }
    throw new Error(message);
  }
  return response.json();
}
// Persist before sending. Acknowledged IDs are removed only after the server commits.
// Serial writes preserve ordering across a retry and a late network response.
type Pending = { id: string; path: string; body: unknown };
const key = "fruit-shift-outbox-v1";
let sending: Promise<void> | null = null;
export function pending(): Pending[] {
  return JSON.parse(localStorage.getItem(key) || "[]");
}
export function queue(id: string, path: string, body: unknown) {
  const items = pending();
  if (!items.some((i) => i.id === id)) {
    items.push({ id, path, body });
    localStorage.setItem(key, JSON.stringify(items));
  }
}
export function flush(): Promise<void> {
  if (sending) return sending;
  sending = (async () => {
    while (pending().length) {
      const item = pending()[0];
      await api(item.path, item.body);
      localStorage.setItem(
        key,
        JSON.stringify(pending().filter((i) => i.id !== item.id)),
      );
    }
  })().finally(() => {
    sending = null;
  });
  return sending;
}
