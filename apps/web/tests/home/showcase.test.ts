import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { showcaseDefaults, showcaseProjects } from "../../src/showcase-projects.ts";

test("showcase projects provide a cover, process, and prompt for each media type", () => {
  assert.equal(showcaseProjects.length, 4);
  assert.deepEqual(showcaseProjects.map((project) => project.type), ["网页", "图片", "音乐", "视频"]);
  assert.ok(showcaseProjects.every((project) => project.cover && project.process.length === 3 && project.prompt));
});

test("showcase defaults keep the student gallery compact and reviewable", () => {
  assert.equal(showcaseDefaults.columns * showcaseDefaults.rows, 8);
  assert.equal(showcaseDefaults.requireReview, true);
});

test("home showcase reads approved works and the organization display rule", async () => {
  const source = await readFile(new URL("../../app/components/student-showcase.tsx", import.meta.url), "utf8");
  assert.match(source, /getStudentAccess/);
  assert.match(source, /listShowcaseWorks/);
  assert.match(source, /showcaseColumns \* nextSettings\.showcaseRows/);
  assert.match(source, /showcaseSort/);
});
