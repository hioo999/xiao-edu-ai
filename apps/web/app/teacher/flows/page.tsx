"use client";

import { useEffect, useState } from "react";

import { currentSession, listCourses, ManagedCourse } from "../../../src/api-client";

export default function TeacherFlowsPage() {
  const [courses, setCourses] = useState<ManagedCourse[]>([]);
  const [status, setStatus] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (!session) return setStatus("请先登录教师账号。");
    void listCourses(session.accessToken).then(setCourses).catch(() => setStatus("无法读取课程。"));
  }, []);

  return (
    <main className="teacher-shell">
      <header className="teacher-home-header"><div><p className="student-home__eyebrow">TEACHING FLOW</p><h1>教学流程</h1><p>查看每节课的步骤、提示词和学生端流程，点击进入课程编辑。</p></div><a className="teacher-primary-link" href="/teacher/courses">管理课程 →</a></header>
      {status && <div className="settings-note">{status}</div>}
      <div className="teacher-card-grid">
        {courses.map((course) => <article className="teacher-card" key={course.courseId}>
          <span>教学流程 · {course.published ? "已发布" : "草稿"}</span>
          <h2>{course.title}</h2>
          <p>{course.studentFlow.length ? `共 ${course.studentFlow.length} 个步骤，学生按顺序完成。` : "尚未编排学生流程。"}</p>
          <ol className="flow-steps">{course.studentFlow.slice(0, 5).map((step) => <li key={step}>{step}</li>)}</ol>
          <a className="teacher-secondary-link" href={`/teacher/courses/${encodeURIComponent(course.courseId)}`}>编辑流程 →</a>
        </article>)}
        {courses.length === 0 && <article className="teacher-card"><span>空</span><h2>还没有课程</h2><p>先创建课程，再编排教学流程和学生提示词。</p><a className="teacher-primary-link" href="/teacher/courses">去创建课程</a></article>}
      </div>
    </main>
  );
}
