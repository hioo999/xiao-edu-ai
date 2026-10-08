"use client";

import { FormEvent, useEffect, useState } from "react";

import { createClassroom, currentSession, listClassrooms, ManagedClassroom, setClassroomState } from "../../../src/api-client";

export default function TeacherClassesPage() {
  const [classrooms, setClassrooms] = useState<ManagedClassroom[]>([]);
  const [classId, setClassId] = useState("");
  const [status, setStatus] = useState("");

  async function refresh() {
    const session = currentSession();
    if (!session) return;
    try {
      setClassrooms(await listClassrooms(session.accessToken));
    } catch {
      setStatus("无法读取班级列表。");
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    const session = currentSession();
    if (!session || !classId.trim()) return setStatus("请填写班级编号。");
    try {
      await createClassroom(session.accessToken, classId.trim());
      setClassId("");
      setStatus(`班级 ${classId.trim()} 已创建，你已自动成为该班教师。`);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "创建班级失败。");
    }
  }

  async function changeState(classroom: ManagedClassroom, next: "open" | "paused" | "closed") {
    const session = currentSession();
    if (!session) return;
    try {
      await setClassroomState(session.accessToken, classroom.classId, next);
      await refresh();
      setStatus(`班级 ${classroom.classId} 已${next === "open" ? "开放" : next === "paused" ? "暂停" : "结束"}。`);
    } catch {
      setStatus("班级状态更新失败。");
    }
  }

  return (
    <main className="teacher-shell">
      <header className="teacher-home-header"><div><p className="student-home__eyebrow">MY CLASSES</p><h1>班级管理</h1><p>创建班级、开放课堂，并随时进入实时监看。</p></div><a className="teacher-primary-link" href="/teacher/classroom">进入实时课堂 →</a></header>
      <section className="section-workspace">
        <form className="settings-form" onSubmit={create}>
          <label>新班级编号<input value={classId} onChange={(event) => setClassId(event.target.value)} placeholder="例如 class-3-2" required /></label>
          <button className="teacher-primary-link" type="submit">创建班级</button>
        </form>
        {status && <div className="settings-note">{status}</div>}
        <div className="backoffice-table">
          <div><span>班级</span><span>状态</span><span>在线学生</span><span>需要帮助</span><span>操作</span></div>
          {classrooms.map((classroom) => <div key={classroom.classId}><strong>{classroom.classId}</strong><span className="status-pill">{classroom.state === "open" ? "开放中" : classroom.state === "paused" ? "已暂停" : "已结束"}</span><span>{classroom.onlineStudents}</span><span>{classroom.helpNeeded}</span><span><a className="teacher-secondary-link" href={`/teacher/classroom?classId=${encodeURIComponent(classroom.classId)}`}>监看</a><button onClick={() => void changeState(classroom, classroom.state === "open" ? "paused" : "open")}>{classroom.state === "open" ? "暂停" : "开放"}</button><button onClick={() => void changeState(classroom, "closed")}>结束</button></span></div>)}
          {classrooms.length === 0 && <div><span>还没有班级</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}
        </div>
      </section>
    </main>
  );
}
