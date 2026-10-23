import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { showcaseDefaults, showcaseProjects } from "../../src/showcase-projects.ts";

test("showcase fallback provides eight honest inspiration cards and a playable video sample", () => {
  assert.equal(showcaseProjects.length, 8);
  assert.ok(showcaseProjects.every((project) => project.cover && project.process.length === 3 && project.prompt));
  assert.equal(showcaseProjects.find((project) => project.id === "magic-brush")?.previewUrl, "/samples/magic-brush.mp4");
  assert.ok(showcaseProjects.every((project) => !("likes" in project) && !("favorites" in project)));
});

test("showcase defaults keep the student gallery compact and reviewable", () => {
  assert.equal(showcaseDefaults.columns * showcaseDefaults.rows, 8);
  assert.equal(showcaseDefaults.requireReview, true);
});

test("home showcase reads approved works and the organization display rule", async () => {
  const source = await readFile(new URL("../../app/components/student-showcase.tsx", import.meta.url), "utf8");
  const styles = await readFile(new URL("../../app/creative-island.css", import.meta.url), "utf8");
  assert.match(source, /getStudentAccess/);
  assert.match(source, /listShowcaseWorks/);
  assert.match(source, /nextSettings\.showcaseKind, 8, "popular"/);
  assert.match(source, /"popular"/);
  assert.match(source, /works\/examples/);
  assert.match(source, /--showcase-columns/);
  assert.doesNotMatch(source, /gridTemplateColumns:/);
  assert.match(styles, /repeat\(var\(--showcase-columns,4\),minmax\(0,1fr\)\)/);
  assert.match(styles, /@media\s*\(max-width:560px\)/);
  assert.match(styles, /\.student-showcase__grid\{grid-template-columns:1fr\}/);
});

test("creative book remains visible on narrow screens", async () => {
  const styles = await readFile(new URL("../../app/creative-island.css", import.meta.url), "utf8");
  const narrowScreenRule = styles.match(/@media \(max-width:900px\) \{ \.kids-3d-scene[^\n]+/)?.[0];
  assert.ok(narrowScreenRule);
  assert.match(narrowScreenRule, /\.creative-book-canvas \{ display:block; \}/);
});
