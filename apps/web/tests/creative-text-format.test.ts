import assert from "node:assert/strict";
import test from "node:test";

import { parseCreativeText } from "../src/creative-text-format.ts";

test("creative text parser turns markdown heading into centered title block data", () => {
  assert.deepEqual(parseCreativeText("## 我的妈妈\n我的妈妈很温柔。\n她每天陪我读书。"), [
    { kind: "heading", level: 2, text: "我的妈妈" },
    { kind: "paragraph", text: "我的妈妈很温柔。" },
    { kind: "paragraph", text: "她每天陪我读书。" },
  ]);
});

test("creative text parser strips simple markdown while keeping paragraph text", () => {
  assert.deepEqual(parseCreativeText("# **春天来了**\n\n- 小草发芽了，花儿也开了。"), [
    { kind: "heading", level: 1, text: "春天来了" },
    { kind: "paragraph", text: "小草发芽了，花儿也开了。" },
  ]);
});
