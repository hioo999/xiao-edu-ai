import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("Skill 管理页可编辑教学规则并保存到后端", async () => {
  const [manager, client] = await Promise.all([
    readFile(new URL("../app/admin/components/tool-manager.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/api-client.ts", import.meta.url), "utf8"),
  ]);

  assert.match(manager, /教学规则/);
  assert.match(manager, /instruction/);
  assert.match(manager, /编辑/);
  assert.match(manager, /text, html, image, music, video/);
  assert.match(client, /instruction: string/);
});

test("提示词润色后台可恢复课堂推荐样本", async () => {
  const [page, client] = await Promise.all([
    readFile(new URL("../app/admin/polish/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/api-client.ts", import.meta.url), "utf8"),
  ]);

  assert.match(page, /恢复默认样本/);
  assert.match(page, /resetPromptPolishPolicy/);
  assert.match(client, /policies\/\$\{capability\}\/reset/);
  assert.match(page, /AdminPageLayout/);
  assert.match(page, /aria-label=\{`\$\{policy\.name\}润色系统提示词`\}/);
  assert.match(page, /rows=\{12\}/);
});
