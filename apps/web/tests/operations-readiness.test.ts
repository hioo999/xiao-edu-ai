import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("运维后台展示 AgentScope 预检项而非笼统状态", async () => {
  const [page, client] = await Promise.all([
    readFile(new URL("../app/admin/operations/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/api-client.ts", import.meta.url), "utf8"),
  ]);

  assert.match(client, /interface AgentReadiness/);
  assert.match(client, /checks:/);
  assert.match(page, /AgentScope 预检项/);
  assert.match(page, /Gateway 模式（可用）/);
});
