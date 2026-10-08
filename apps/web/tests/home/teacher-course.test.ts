import assert from "node:assert/strict";
import { test } from "node:test";

import { teacherCourses } from "../../src/teacher-courses.ts";

test("teacher courses include scripts, prompts, and student-facing flow", () => {
  assert.ok(teacherCourses.length >= 2);
  assert.ok(teacherCourses.every((course) => course.transcript.length > 0));
  assert.ok(teacherCourses.every((course) => course.prompts.length > 0));
  assert.ok(teacherCourses.every((course) => course.flow.length > 0));
});
