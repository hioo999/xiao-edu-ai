import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { adminNavigation, studentNavigation, teacherNavigation } from "../src/navigation.ts";

const appRoot = join(import.meta.dirname, "..", "app");

function routeExists(href: string): boolean {
  const segments = href.split("/").filter(Boolean);
  if (existsSync(join(appRoot, ...segments, "page.tsx")) || existsSync(join(appRoot, ...segments, "page.ts"))) return true;
  const parent = segments.slice(0, -1);
  return ["kind", "section"].some((parameter) => existsSync(join(appRoot, ...parent, `[${parameter}]`, "page.tsx")) || existsSync(join(appRoot, ...parent, `[${parameter}]`, "page.ts")));
}

test("all student, teacher, and admin navigation entries resolve to pages", () => {
  const unresolved = [...studentNavigation, ...teacherNavigation, ...adminNavigation]
    .filter((item) => !routeExists(item.href))
    .map((item) => item.href);

  assert.deepEqual(unresolved, []);
});
