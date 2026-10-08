import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { test } from "node:test";

const appRoot = new URL("../../app/", import.meta.url);

test("student home destinations have matching app routes", () => {
  const destinations = [
    "page.tsx",
    "inspiration/page.tsx",
    "projects/page.tsx",
    "courses/page.tsx",
    "student/reports/page.tsx",
    "workspace/[kind]/page.tsx",
    "workspace/html/page.tsx",
    "agents/page.tsx",
    "works/[id]/page.tsx",
    "share/[token]/page.tsx",
    "showcase/page.tsx",
    "admin/providers/page.tsx",
    "teacher/courses/page.tsx",
    "teacher/courses/[id]/page.tsx",
  ];

  for (const destination of destinations) {
    assert.equal(existsSync(new URL(destination, appRoot)), true, `missing route: ${destination}`);
  }
});
