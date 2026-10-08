"use client";

import { useEffect, useMemo, useState } from "react";

import { currentSession, getStudentLearningReport, listClassroomStudents, listClassrooms, LearningReport, ManagedClassroom } from "../../../src/api-client";

type ReportRow = { studentId: string; lessons: number; submitted: number; reviewed: number; hasReport: boolean };

export default function TeacherReportsPage() {
  const [classrooms, setClassrooms] = useState<ManagedClassroom[]>([]);
  const [classId, setClassId] = useState("");
  const [rows, setRows] = useState<ReportRow[]>([]);
  const [status, setStatus] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (session) void listClassrooms(session.accessToken).then((items) => { setClassrooms(items); setClassId(items[0]?.classId ?? ""); }).catch(() => setStatus("无法读取班级列表。"));
  }, []);

  useEffect(() => {
    const session = currentSession();
    if (!session || !classId) { setRows([]); return; }
    let cancelled = false;
    void (async () => {
      try {
        const students = await listClassroomStudents(session.accessToken, classId);
        const reports = await Promise.all(students.map(async (student) => {
          try {
            const report: LearningReport = await getStudentLearningReport(session.accessToken, student.studentId);
            return { studentId: student.studentId, lessons: report.completedLessons.length, submitted: report.submittedAssignments.length, reviewed: report.reviewedAssignments.length, hasReport: true };
          } catch {
            return { studentId: student.studentId, lessons: 0, submitted: 0, reviewed: 0, hasReport: false };
          }
        }));
        if (!cancelled) setRows(reports);
      } catch {
        if (!cancelled) setStatus("无法读取学生报告。");
      }
    })();
    return () => { cancelled = true; };
  }, [classId]);

  const summary = useMemo(() => ({ withReport: rows.filter((row) => row.hasReport).length, totalLessons: rows.reduce((sum, row) => sum + row.lessons, 0), totalSubmitted: rows.reduce((sum, row) => sum + row.submitted, 0) }), [rows]);

  return (
    <main className="teacher-shell">
      <header className="teacher-home-header"><div><p className="student-home__eyebrow">LEARNING REPORTS</p><h1>学习报告</h1><p>汇总每个学生的课程完成、作业提交和批改情况。</p></div></header>
      <div className="teacher-toolbar"><div><select value={classId} onChange={(event) => setClassId(event.target.value)}>{classrooms.map((item) => <option key={item.classId} value={item.classId}>{item.classId}</option>)}</select></div><div className="teacher-toolbar__actions"><span>{summary.withReport} 人已有报告 · 共完成 {summary.totalLessons} 课 · 提交作业 {summary.totalSubmitted} 次</span></div></div>
      {status && <div className="settings-note">{status}</div>}
      <div className="backoffice-table">
        <div><span>学生</span><span>完成课程</span><span>提交作业</span><span>已批改</span><span>状态</span></div>
        {rows.map((row) => <div key={row.studentId}><strong>{row.studentId}</strong><span>{row.lessons}</span><span>{row.submitted}</span><span>{row.reviewed}</span><span className="status-pill">{row.hasReport ? "有报告" : "暂无记录"}</span></div>)}
        {rows.length === 0 && <div><span>暂无学生</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}
      </div>
    </main>
  );
}
