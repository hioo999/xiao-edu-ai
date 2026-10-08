import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("assets page reads real student works and provides media filters", async () => {
  const source = await readFile(new URL("../app/assets/page.tsx", import.meta.url), "utf8");

  assert.match(source, /listMyWorks/);
  assert.match(source, /图片.*音乐.*视频.*网页/s);
  assert.match(source, /\/works\/\$\{work\.assetId\}/);
});
