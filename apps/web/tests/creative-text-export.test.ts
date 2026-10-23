import assert from "node:assert/strict";
import test from "node:test";

import { buildWordDocument, safeDownloadName } from "../src/creative-text-export.ts";

test("word export keeps formatted title and paragraphs while escaping content", () => {
  const document = buildWordDocument("我的妈妈", "## 我的妈妈\n她每天陪我读书。\n\n她也会听我讲学校的故事。<script>");
  assert.match(document, /<h2>我的妈妈<\/h2>/);
  assert.match(document, /<p>她每天陪我读书。<\/p>/);
  assert.match(document, /&lt;script&gt;/);
  assert.doesNotMatch(document, /<script>/);
});

test("download filename removes characters that are invalid on common systems", () => {
  assert.equal(safeDownloadName("我的妈妈:/结果"), "我的妈妈 结果");
  assert.equal(safeDownloadName(""), "AI创作结果");
});
