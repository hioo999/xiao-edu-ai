"use client";
import { useEffect, useState } from "react";
import TeacherCoursesPage from "../../teacher/courses/page";
import { currentSession, listCourseReviewQueue, ManagedCourse, reviewCourse } from "../../../src/api-client";
import { AdminShell } from "../components/admin-shell";

export default function CoursesAdminPage() {
  const [queue, setQueue] = useState<ManagedCourse[]>([]);
  const [message, setMessage] = useState("");
  useEffect(() => { const session = currentSession(); if (session) void listCourseReviewQueue(session.accessToken).then(setQueue).catch((error) => setMessage(error instanceof Error ? error.message : "审核队列读取失败")); }, []);
  async function act(courseId: string, action: "approve" | "reject") { const session = currentSession(); if (!session) return; try { await reviewCourse(session.accessToken, courseId, action, action === "reject" ? "请补充完整课程内容后重新提交。" : "审核通过"); setQueue((items) => items.filter((item) => item.courseId !== courseId)); setMessage(action === "approve" ? "课程已通过审核。" : "课程已驳回。"); } catch (error) { setMessage(error instanceof Error ? error.message : "审核操作失败"); } }
  return <AdminShell active="/admin/courses"><div className="admin-course-page"><section className="teacher-shell"><div className="course-editor-header"><div><p className="student-home__eyebrow">COURSE REVIEW</p><h1>课程审核</h1><p>审核教师提交的课程，确认课件、教学内容和逐字稿完整后再发布。</p></div><span className="status-pill">待审核 {queue.length}</span></div>{message && <p className="course-upload-status">{message}</p>}<div className="teacher-card-grid">{queue.length ? queue.map((course) => <article className="teacher-card" key={course.courseId}><span>待审核 · {course.courseId}</span><h2>{course.title}</h2><p>{course.summary || "暂无课程简介"}</p><p>{course.blocks.length || course.studentFlow.length} 个教学步骤</p><div><button className="teacher-primary-link" type="button" onClick={() => void act(course.courseId, "approve")}>通过</button><button className="teacher-secondary-link" type="button" onClick={() => void act(course.courseId, "reject")}>驳回</button></div></article>) : <p>当前没有待审核课程。</p>}</div></section><TeacherCoursesPage /></div></AdminShell>;
}
