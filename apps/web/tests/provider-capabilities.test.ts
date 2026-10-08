import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const providersPage = readFileSync("app/admin/providers/page.tsx", "utf8");
const adminHome = readFileSync("app/admin/page.tsx", "utf8");

test("AI 能力中心将音乐作为第四类独立能力配置", () => {
  assert.match(providersPage, /type Capability = "text" \| "image" \| "video" \| "music";/);
  assert.match(providersPage, /music: \{ label: "音乐模型"/);
  assert.match(providersPage, /music: \[/);
});

test("音乐能力提供豆包、通义、可灵和 MiniMax 预设入口", () => {
  assert.match(providersPage, /火山方舟（豆包音乐 \/ SeedMusic）/);
  assert.match(providersPage, /阿里云百炼（通义万相音乐）/);
  assert.match(providersPage, /可灵 AI Kling 音乐/);
  assert.match(providersPage, /MiniMax 海螺音乐/);
  assert.match(providersPage, /doubaoMusic/);
  assert.match(providersPage, /qwenMusic/);
});

test("平台运营总览同步展示音乐能力状态", () => {
  assert.match(adminHome, /\["text", "image", "video", "music"\]/);
  assert.match(adminHome, /"音乐模型"/);
});
