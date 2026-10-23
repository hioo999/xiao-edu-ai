import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("admin shell has accessible navigation and operational status", async () => {
  const source = await readFile(new URL("../app/admin/components/admin-shell.tsx", import.meta.url), "utf8");
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(source, /aria-label="后台主导航"/);
  assert.match(source, /role="status"/);
  assert.match(source, /aria-label=\{roleLabel\}/);
  assert.match(styles, /--admin-bg/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.match(styles, /admin-sidebar/);
});

test("admin navigation keeps all operational domains visible", async () => {
  const source = await readFile(new URL("../app/admin/components/admin-shell.tsx", import.meta.url), "utf8");
  for (const label of ["教学运营", "AI 能力中心", "平台治理", "课程与教学", "安全与审计", "Skills", "MCP 工具", "知识库"]) {
    assert.match(source, new RegExp(label));
  }
  assert.doesNotMatch(source, /admin-utility-links/);
  assert.match(source, /active === item\.href/);
});

test("admin inner pages use a shared hierarchy", async () => {
  const layout = await readFile(new URL("../app/admin/components/admin-page-layout.tsx", import.meta.url), "utf8");
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(layout, /admin-page-layout__header/);
  assert.match(layout, /admin-section__header/);
  assert.match(styles, /\.admin-page-layout__header/);
  assert.match(styles, /\.admin-section__toolbar/);
  assert.match(styles, /\.admin-page-layout \.admin-log-table/);
  assert.match(styles, /max-height:none/);
});

test("tool management pages expose their own active navigation", async () => {
  const skills = await readFile(new URL("../app/admin/skills/page.tsx", import.meta.url), "utf8");
  const mcp = await readFile(new URL("../app/admin/mcp/page.tsx", import.meta.url), "utf8");
  assert.match(skills, /active="\/admin\/skills"/);
  assert.match(mcp, /active="\/admin\/mcp"/);
});

test("admin visual system isolates reused course content from student styling", async () => {
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  const courses = await readFile(new URL("../app/admin/courses/page.tsx", import.meta.url), "utf8");
  assert.match(styles, /\.admin-shell \.teacher-shell/);
  assert.match(styles, /\.admin-shell \.settings-form/);
  assert.match(styles, /\.admin-shell \.admin-log-table/);
  assert.match(styles, /max-height: 74px/);
  assert.match(courses, /<AdminShell active="\/admin\/courses">/);
});
