import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("admin assets page supports safe HTML and ZIP project uploads", async () => {
  const source = await readFile(new URL("../app/admin/assets/page.tsx", import.meta.url), "utf8");
  assert.match(source, /uploadExternalWork/);
  assert.match(source, /\.html,.htm,.zip/);
  assert.match(source, /不会在平台服务器直接执行/);
  assert.match(source, /listStudents/);
  assert.match(source, /multiple accept=/);
  assert.match(source, /WorkDeployment/);
  assert.match(source, /工程部署与预览/);
  assert.match(source, /manifest\.dependencies\.length/);
  assert.match(source, /登记 HTTPS 预览地址/);
  assert.match(source, /publishWorkDeployment/);
});

test("api client exposes deployment preparation and listing endpoints", async () => {
  const source = await readFile(new URL("../src/api-client.ts", import.meta.url), "utf8");
  assert.match(source, /prepareWorkDeployment/);
  assert.match(source, /listWorkDeployments/);
  assert.match(source, /publishWorkDeployment/);
  assert.match(source, /deployments\/prepare/);
  assert.match(source, /deployments.*publish/);
  assert.match(source, /deployments`/);
});

test("showcase administration supports safe cover and preview uploads", async () => {
  const page = await readFile(new URL("../app/admin/showcase/page.tsx", import.meta.url), "utf8");
  const client = await readFile(new URL("../src/api-client.ts", import.meta.url), "utf8");
  assert.match(page, /上传封面图/);
  assert.match(page, /上传预览文件/);
  assert.match(client, /uploadWorkMedia/);
  assert.match(client, /resolveWorkMediaUrl/);
});

test("generated webpage preview stays isolated from the platform origin", async () => {
  const page = await readFile(new URL("../app/works/[id]/page.tsx", import.meta.url), "utf8");
  assert.match(page, /sandbox="allow-scripts" srcDoc=\{html\}/);
  assert.doesNotMatch(page, /sandbox="allow-scripts allow-same-origin"/);
});
