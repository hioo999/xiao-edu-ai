import { test } from "node:test";
import assert from "node:assert/strict";

import { platformTitle } from "../src/platform-title.ts";

test("exposes the product title for the student shell", () => {
  assert.equal(platformTitle, "星芽 AI 创作岛");
});
