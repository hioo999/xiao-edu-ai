"use client";

import { useEffect, useRef, useState } from "react";

import { currentSession, listCourses, ManagedCourse, uploadCourseMaterial } from "../../../src/api-client";
import { defaultCourseUploadTypes, teacherCourses } from "../../../src/teacher-courses";

export default function TeacherCoursesPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [courses, setCourses] = useState<ManagedCourse[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    void listCourses(session.accessToken).then((items) => {
      setCourses(items);
      setSelectedCourseId((current) => current || items[0]?.courseId || "");
    }).catch(() => setUploadStatus("暂时无法读取服务端课程，正在显示课程模板。"));
  }, []);

  async function handleUpload(file: File | undefined) {
    if (!file || !selectedCourseId) return setUploadStatus("请先创建或选择一节课程，再上传课件。");
    const session = currentSession();
    if (!session) return setUploadStatus("请先登录教师账号。");
    try {
      await uploadCourseMaterial(session.accessToken, selectedCourseId, file);
      setUploadStatus(`${file.name} 已上传到当前课程。`);
    } catch (error) { setUploadStatus(error instanceof Error ? error.message : "课件上传失败。"); }
  }

  const cards = courses.length ? courses.map((course) => ({ id: course.courseId, grade: "已保存课程", status: course.published ? "已发布" : "草稿", title: course.title, lessons: course.studentFlow.length || course.blocks.length })) : teacherCourses;

  return (
    <main className="teacher-shell">
      <div className="course-editor-header"><div><p className="student-home__eyebrow">TEACHER STUDIO</p><h1>课程编辑器</h1><p>把文字、图片、视频、只读代码块、步骤和挑战组合成一节 AI 课程。</p></div><a className="teacher-primary-link" href="/teacher/courses/new">＋ 新建课程</a></div>
      <section className="course-upload-card"><div><strong>上传课件</strong><p>课件会归入选中的课程，学生不会直接看到教师逐字稿和提示词。</p><div className="course-upload-types">{defaultCourseUploadTypes.map((type) => <span key={type}>{type}</span>)}</div>{uploadStatus && <small className="course-upload-status">{uploadStatus}</small>}</div><div><select aria-label="选择课程" value={selectedCourseId} onChange={(event) => setSelectedCourseId(event.target.value)}><option value="">选择已保存课程</option>{courses.map((course) => <option key={course.courseId} value={course.courseId}>{course.title}</option>)}</select><input ref={inputRef} type="file" hidden onChange={(event) => void handleUpload(event.target.files?.[0])} /><button className="teacher-primary-link" type="button" onClick={() => inputRef.current?.click()}>＋ 选择文件</button></div></section>
      <div className="teacher-card-grid">{cards.map((course) => <article className="teacher-card" key={course.id}><span>{course.grade} · {course.status}</span><h2>{course.title}</h2><p>{course.lessons} 个教学步骤 · 含逐字稿和提示词</p><a className="teacher-card-link" href={`/teacher/courses/${course.id}`}>编辑课件 →</a></article>)}</div>
    </main>
  );
}
