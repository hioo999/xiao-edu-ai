import assert from "node:assert/strict";
import { test } from "node:test";

import { apiUrl, sessionFromLoginResponse, textGenerationFromResponse } from "../src/api-client.ts";

test("api client builds versioned API URLs without exposing provider keys", () => {
  assert.equal(apiUrl("/auth/login"), "http://127.0.0.1:8000/auth/login");
  assert.equal(apiUrl("/auth/login", "http://localhost:8000"), "http://localhost:8000/auth/login");
  assert.equal(apiUrl("projects/project-001/html/generate", "http://localhost:8000/"), "http://localhost:8000/projects/project-001/html/generate");
});

test("login response becomes a browser-safe platform session", () => {
  const session = sessionFromLoginResponse({
    userId: "student-001",
    organizationId: "org-001",
    role: "student",
    accessToken: "opaque-access-token",
    expiresAt: "2026-09-24T10:00:00+00:00",
  });

  assert.equal(session.role, "student");
  assert.equal(session.accessToken, "opaque-access-token");
  assert.equal("apiKey" in session, false);
});

test("text generation response never contains a provider secret", () => {
  assert.deepEqual(textGenerationFromResponse({ content: "你好", providerId: "platform-deepseek-text", modelId: "deepseek-chat" }), {
    content: "你好", providerId: "platform-deepseek-text", modelId: "deepseek-chat",
  });
});
