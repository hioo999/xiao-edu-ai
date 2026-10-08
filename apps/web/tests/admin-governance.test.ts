import assert from "node:assert/strict";
import { test } from "node:test";

import { assistStudent, checkModerationContent, getModerationPolicy, getStudentClassroomView, myLearningReport, saveModerationPolicy } from "../src/api-client.ts";

function stubFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const original = globalThis.fetch;
  globalThis.fetch = handler as typeof fetch;
  return () => { globalThis.fetch = original; };
}

test("moderation policy reads blocked terms from the admin contract", async () => {
  const restore = stubFetch(async (input, init) => {
    assert.equal(String(input).endsWith("/moderation/policy"), true);
    assert.equal((init?.headers as Record<string, string>).Authorization, "Bearer token");
    return new Response(JSON.stringify({ enabled: true, modes: ["classroom"], status: "active", blockedTerms: ["危险词"] }), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  try {
    const policy = await getModerationPolicy("token");
    assert.deepEqual(policy.blockedTerms, ["危险词"]);
    assert.equal(policy.enabled, true);
  } finally {
    restore();
  }
});

test("saving moderation policy sends a PUT with the updated terms", async () => {
  let captured = "";
  const restore = stubFetch(async (input, init) => {
    assert.equal(init?.method, "PUT");
    captured = String(init?.body);
    return new Response(JSON.stringify({ enabled: false, modes: ["classroom", "free_creation"], status: "paused", blockedTerms: ["危险词"] }), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  try {
    const policy = await saveModerationPolicy("token", { enabled: false, blockedTerms: ["危险词"] });
    assert.equal(policy.status, "paused");
    assert.match(captured, /危险词/);
  } finally {
    restore();
  }
});

test("content check reports blocked without throwing", async () => {
  const restore = stubFetch(async () => new Response(null, { status: 422 }));
  try {
    const result = await checkModerationContent("token", "危险内容", "classroom");
    assert.equal(result.decision, "blocked");
  } finally {
    restore();
  }
});

test("student growth report parses completed lessons and homework", async () => {
  const restore = stubFetch(async (input) => {
    assert.equal(String(input).endsWith("/reports/me"), true);
    return new Response(JSON.stringify({ studentId: "student-001", completedLessons: ["第一节"], submittedAssignments: ["作业一"], reviewedAssignments: ["作业一"], aiGenerated: true }), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  try {
    const report = await myLearningReport("token");
    assert.equal(report.completedLessons[0], "第一节");
    assert.equal(report.aiGenerated, true);
  } finally {
    restore();
  }
});

test("teacher can open a student assisted view and grant help", async () => {
  const calls: { url: string; method: string; body: string }[] = [];
  const restore = stubFetch(async (input, init) => {
    calls.push({ url: String(input), method: init?.method ?? "GET", body: String(init?.body ?? "") });
    if (String(input).endsWith("/view")) {
      return new Response(JSON.stringify({ classId: "class-001", studentId: "student-001", mode: "assisted_view", readOnly: false, activeFeature: "html", taskState: "composing", lessonStep: 2, helpNeeded: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify({ granted: true }), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  try {
    const view = await getStudentClassroomView("token", "class-001", "student-001");
    await assistStudent("token", "class-001", "student-001");
    assert.equal(view.activeFeature, "html");
    assert.equal(view.lessonStep, 2);
    assert.equal(calls[0].method, "GET");
    assert.equal(calls[1].method, "POST");
    assert.match(calls[1].body, /student-001/);
  } finally {
    restore();
  }
});
