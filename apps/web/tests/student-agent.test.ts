import assert from "node:assert/strict";
import { test } from "node:test";

import { buildStudentAgentPrompt } from "../src/student-agent.ts";

test("student agent keeps instructions and prior turns when answering a follow-up", () => {
  const prompt = buildStudentAgentPrompt("你是故事向导，要先讲故事", [
    { role: "student", text: "写一段小兔子故事" },
    { role: "assistant", text: "小兔子来到月球花园。" },
  ], "它后来做了什么？");
  assert.match(prompt, /你是故事向导，要先讲故事/);
  assert.match(prompt, /小兔子来到月球花园/);
  assert.match(prompt, /它后来做了什么/);
});
