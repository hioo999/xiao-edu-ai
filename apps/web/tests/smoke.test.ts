import { test } from "node:test";
import assert from "node:assert/strict";

import { platformTitle } from "../src/platform-title.ts";

test("exposes the product title for the student shell", () => {
  assert.equal(platformTitle, "AI 创造力学习工作台");
});
