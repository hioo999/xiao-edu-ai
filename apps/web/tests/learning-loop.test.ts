import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("student courses page closes the learning loop with progress and homework", async () => {
  const source = await readFile(new URL("../app/courses/page.tsx", import.meta.url), "utf8");
  assert.match(source, /upsertLearningProgress/);
  assert.match(source, /submitHomework/);
  assert.match(source, /完成本节课/);
  assert.match(source, /course-progress-box/);
});

test("teacher course editor surfaces class progress and homework annotation", async () => {
  const source = await readFile(new URL("../app/teacher/courses/[id]/page.tsx", import.meta.url), "utf8");
  assert.match(source, /listCourseLearningProgress/);
  assert.match(source, /listCourseHomework/);
  assert.match(source, /annotateHomework/);
  assert.match(source, /学习进度与作业/);
});

test("api client wires learning endpoints to the backend contract", async () => {
  const source = await readFile(new URL("../src/api-client.ts", import.meta.url), "utf8");
  assert.match(source, /\/learning\/progress\//);
  assert.match(source, /\/learning\/courses\/\$\{/);
  assert.match(source, /\/learning\/submissions\//);
});
