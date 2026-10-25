import { test } from "node:test";
import assert from "node:assert/strict";
import { flush, pending, queue } from "./api.ts";

test("the durable outbox retries the exact body and serializes concurrent flushes", async () => {
  const values = new Map<string, string>();
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: storage,
    configurable: true,
  });
  const originalFetch = globalThis.fetch;
  const sent: string[] = [];
  const body = {
    event_id: "stable-id",
    action: "slice",
    presentation_id: "fruit-1",
  };
  try {
    queue("stable-id", "/rounds/round-1/events", body);
    queue("stable-id", "/rounds/round-1/events", body);
    assert.equal(pending().length, 1);
    globalThis.fetch = async () => {
      throw new Error("offline");
    };
    await assert.rejects(flush(), /offline/);
    assert.deepEqual(pending()[0].body, body);
    globalThis.fetch = async (_url, options) => {
      sent.push(options?.body as string);
      return new Response(JSON.stringify({ saved: true }), { status: 200 });
    };
    await Promise.all([flush(), flush(), flush()]);
    assert.equal(sent.length, 1);
    assert.deepEqual(JSON.parse(sent[0]), body);
    assert.equal(pending().length, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
