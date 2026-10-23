import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("only the administrator settings page offers video duration selection", () => {
  const admin = readFileSync(new URL("../app/admin/settings/page.tsx", import.meta.url), "utf8");
  const student = readFileSync(new URL("../app/components/creative-workspace.tsx", import.meta.url), "utf8");

  assert.match(admin, /学生视频生成时长/);
  assert.match(admin, /<option value=\{5\}>5 秒<\/option>/);
  assert.match(admin, /<option value=\{10\}>10 秒<\/option>/);
  assert.match(student, /视频时长由管理员统一设置/);
  assert.doesNotMatch(student, /<PresetChips label="视频时长"/);
});
