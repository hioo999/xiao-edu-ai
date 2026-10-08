import assert from "node:assert/strict";
import { test } from "node:test";

import { adminNavigation, studentNavigation, teacherNavigation } from "../src/navigation.ts";

test("student navigation covers every planned student section", () => {
  assert.deepEqual(
    studentNavigation.map((item) => item.id),
    ["chat", "html", "image", "music", "video", "agents", "inspiration", "projects", "courses", "assets", "reports"],
  );
});

test("teacher and administrator navigation expose their complete workbenches", () => {
  assert.equal(teacherNavigation.length, 9);
  assert.equal(adminNavigation.length, 11);
  assert.ok(teacherNavigation.some((item) => item.id === "review"));
  assert.ok(adminNavigation.some((item) => item.id === "providers"));
});
