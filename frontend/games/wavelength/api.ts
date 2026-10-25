const base = "/api/games/wavelength";

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(base + path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error("This guess was already saved with different values. Reload to recover your round.");
    throw new Error("We couldn’t reach the game server. Check that the backend is running, then try again. Your current guess is kept here.");
  }
  return response.json() as Promise<T>;
}

export async function download(format: "json" | "csv") {
  const response = await fetch(`${base}/exports/${format}`, { signal: AbortSignal.timeout(12000) });
  if (!response.ok) throw new Error("The download couldn’t be prepared. Check the server and try again.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `common-ground.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
