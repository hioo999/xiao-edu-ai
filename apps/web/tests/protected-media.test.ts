import assert from "node:assert/strict";
import test from "node:test";
import { fetchWorkMedia, protectedMediaPath } from "../src/api-client.ts";

test("generated media and uploaded previews are recognized only on the platform API", () => {
  const base = "http://127.0.0.1:8000";
  assert.equal(protectedMediaPath("http://localhost:8000/generated-assets/job-test.png", base), "/generated-assets/job-test.png");
  assert.equal(protectedMediaPath("/works/art/media/preview", base), "/works/art/media/preview");
  assert.equal(protectedMediaPath("https://foreign.example/generated-assets/job-test.png", base), null);
  assert.equal(protectedMediaPath("http://localhost:9000/generated-assets/job-test.png", base), null);
  assert.equal(protectedMediaPath("//foreign.example/works/art/media/preview", base), null);
  assert.equal(protectedMediaPath("/samples/forest.png", base), null);
  assert.equal(protectedMediaPath("https://user:password@school.example/generated-assets/test.png", "https://school.example"), null);
});

test("protected media supports a reverse-proxy API path prefix", () => {
  assert.equal(protectedMediaPath("https://school.example/api/generated-assets/job-test.png", "https://school.example/api"), "/generated-assets/job-test.png");
  assert.equal(protectedMediaPath("/generated-assets/job-test.png", "https://school.example/api"), "/generated-assets/job-test.png");
});

test("media fetch authenticates local files without leaking credentials to external URLs", async () => {
  const originalFetch = globalThis.fetch;
  const requests: { url: string; options: RequestInit | undefined }[] = [];
  globalThis.fetch = async (input, options) => {
    requests.push({ url: String(input), options });
    return new Response("image", { status: 200 });
  };
  try {
    await fetchWorkMedia("/generated-assets/job-test.png", "test-token");
    await fetchWorkMedia("https://foreign.example/generated-assets/job-test.png", "test-token");
    assert.equal(new Headers(requests[0].options?.headers).get("Authorization"), "Bearer test-token");
    assert.equal(requests[0].options?.cache, "no-store");
    assert.equal(requests[0].options?.redirect, "error");
    assert.equal(new Headers(requests[1].options?.headers).has("Authorization"), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
