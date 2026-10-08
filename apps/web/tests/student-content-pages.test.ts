import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const appRoot = new URL("../app/", import.meta.url);

test("student content pages provide useful empty states instead of blank screens", async () => {
  const [projects, courses, inspiration, workspace, teacherHome] = await Promise.all([
    readFile(new URL("projects/page.tsx", appRoot), "utf8"),
    readFile(new URL("courses/page.tsx", appRoot), "utf8"),
    readFile(new URL("inspiration/page.tsx", appRoot), "utf8"),
    readFile(new URL("components/creative-workspace.tsx", appRoot), "utf8"),
    readFile(new URL("teacher/page.tsx", appRoot), "utf8"),
  ]);

  assert.match(projects, /作品夹正在等你的第一个作品/);
  assert.match(courses, /这里会出现老师发布给你的课程/);
  assert.match(inspiration, /登录后解锁你的灵感收藏夹/);
  assert.match(inspiration, /我的收藏/);
  assert.match(inspiration, /startRouteFor/);
  assert.match(courses, /practiceRoute/);
  assert.match(workspace, /URLSearchParams/);
  assert.match(teacherHome, /listClassrooms/);
  assert.doesNotMatch(teacherHome, /18 \/ 24 名学生在线/);
});
