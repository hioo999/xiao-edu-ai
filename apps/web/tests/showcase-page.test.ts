import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("showcase page provides structured discovery and filtering", async () => {
  const source = await readFile(new URL("../app/showcase/page.tsx", import.meta.url), "utf8");
  assert.match(source, /同学作品展示墙/);
  assert.match(source, /老师精选/);
  assert.match(source, /发现更多作品/);
  assert.match(source, /热门/);
  assert.match(source, /最新/);
  assert.match(source, /搜索作品名称或创意/);
  assert.match(source, /3-4 年级/);
  assert.match(source, /5-6 年级/);
  assert.match(source, /listShowcaseWorks\(session\.accessToken, undefined, 100, sort\)/);
});

test("showcase cards expose detail, like, favorite and fixed media structure", async () => {
  const source = await readFile(new URL("../app/showcase/page.tsx", import.meta.url), "utf8");
  const styles = await readFile(new URL("../app/showcase/showcase.module.css", import.meta.url), "utf8");
  assert.match(source, /href={`\/works\/\$\{work\.assetId\}`}/);
  assert.match(source, /likeWork/);
  assert.match(source, /favoriteWork/);
  assert.match(source, /aria-pressed/);
  assert.match(source, /登录后参观同学们的作品/);
  assert.match(source, /作品墙暂时没有打开/);
  assert.match(styles, /aspect-ratio:4 \/ 3/);
  assert.match(styles, /grid-template-columns:repeat\(4,minmax\(0,1fr\)\)/);
  assert.match(styles, /@media\(max-width:390px\)/);
  assert.match(styles, /prefers-reduced-motion/);
});
