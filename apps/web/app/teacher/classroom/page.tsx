"use client";

import { useEffect, useState } from "react";
import { assistStudent, classroomRequest, ClassroomStudent, currentSession, getStudentClassroomView, listClassrooms, listClassroomStudents, ManagedClassroom, StudentView } from "../../../src/api-client";

const featureLabel: Record<string, string> = { home: "创作大厅", chat: "AI 对话", html: "网页创作", image: "图片创作", music: "音乐创作", video: "视频创作", agents: "智能体中心" };

export default function TeacherClassroomPage() {
  const [classrooms, setClassrooms] = useState<ManagedClassroom[]>([]);
  const [classId, setClassId] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [students, setStudents] = useState<ClassroomStudent[]>([]);
  const [view, setView] = useState<StudentView | null>(null);
  const [status, setStatus] = useState("");
  useEffect(() => { const session = currentSession(); const requestedClassId = new URLSearchParams(window.location.search).get("classId"); if (session) void listClassrooms(session.accessToken).then((items) => { setClassrooms(items); setClassId(requestedClassId && items.some((item) => item.classId === requestedClassId) ? requestedClassId : items[0]?.classId ?? ""); }).catch(() => setStatus("无法读取课堂列表。")); }, []);
  useEffect(() => { const session = currentSession(); const classroom = classrooms.find((item) => item.classId === classId); setIsOpen(classroom?.state === "open"); if (session && classId) void listClassroomStudents(session.accessToken, classId).then(setStudents).catch(() => setStatus("无法读取学生状态。")); }, [classId, classrooms]);
  async function toggleClassroom() { const session = currentSession(); if (!session || !classId) return; const action = isOpen ? "pause" : "open"; try { await classroomRequest(`/classrooms/${encodeURIComponent(classId)}/${action}`, session.accessToken); setIsOpen(!isOpen); setClassrooms((items) => items.map((item) => item.classId === classId ? { ...item, state: isOpen ? "paused" : "open" } : item)); } catch { setStatus("课堂状态更新失败。"); } }
  async function grant(student: ClassroomStudent) { const session = currentSession(); if (!session) return; try { await assistStudent(session.accessToken, classId, student.studentId); setStudents((items) => items.map((item) => item.studentId === student.studentId ? { ...item, assistanceGranted: true } : item)); setStatus(`已进入 ${student.studentId} 的辅导模式。`); } catch { setStatus("进入辅导失败。"); } }
  async function openView(student: ClassroomStudent) { const session = currentSession(); if (!session) return; try { setView(await getStudentClassroomView(session.accessToken, classId, student.studentId)); } catch { setStatus("无法打开学生界面，请先进入辅导模式。"); } }
  if (!classId) return <main className="teacher-shell"><h1>还没有可监看的课堂</h1><p>请先由管理员创建课堂并分配教师。</p><a className="teacher-primary-link" href="/admin/classrooms">进入课堂管理 →</a></main>;
  return (
    <main className="teacher-shell">
      <div className="teacher-toolbar"><div><p className="student-home__eyebrow">CLASSROOM MONITOR</p><h1>{classId} · AI 创作课堂</h1></div><div className="teacher-toolbar__actions"><select value={classId} onChange={(event) => setClassId(event.target.value)}>{classrooms.map((item) => <option key={item.classId} value={item.classId}>{item.classId}</option>)}</select><button onClick={() => void toggleClassroom()}>{isOpen ? "暂停课堂" : "开放课堂"}</button></div></div>
      <p className="classroom-state">当前状态：{isOpen ? "开放中" : "已暂停"} · 教师可以查看学生状态，并对单个学生进入辅导模式。</p>
      {status && <p className="settings-note">{status}</p>}
      <div className="student-monitor-grid">{students.map((student) => <article className="student-monitor-card" key={student.studentId}><div><strong>{student.studentId}</strong><span>{featureLabel[student.activeFeature] ?? student.activeFeature}</span></div><p>{student.helpNeeded ? "需要帮助" : student.taskState}</p><div className="student-monitor-card__actions"><button disabled={!isOpen || student.assistanceGranted} onClick={() => void grant(student)}>{student.assistanceGranted ? "已进入辅导" : "进入辅导"}</button><button disabled={!student.assistanceGranted} onClick={() => void openView(student)}>查看学生界面</button></div></article>)}</div>
      {view && <section className="student-view-panel" aria-label="学生界面"><div className="student-view-panel__head"><div><p className="student-home__eyebrow">ASSISTED VIEW</p><h2>{view.studentId} · {featureLabel[view.activeFeature] ?? view.activeFeature}</h2></div><button type="button" onClick={() => setView(null)}>关闭</button></div><p>辅导模式：{view.readOnly ? "只读" : "可协助"} · 当前在第 {view.lessonStep + 1} 步 · {view.helpNeeded ? "需要帮助" : view.taskState}</p><div className="student-view-panel__body"><span>{view.studentId} 正在使用「{featureLabel[view.activeFeature] ?? view.activeFeature}」功能。</span><a className="teacher-primary-link" href={`/workspace/${view.activeFeature === "agents" ? "chat" : view.activeFeature}`}>打开对应创作界面 →</a></div></section>}
    </main>
  );
}
