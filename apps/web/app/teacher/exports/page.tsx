"use client";

import { useEffect, useState } from "react";

import { currentSession, getStudentLearningReport, listClassroomStudents, listClassrooms, listCourses } from "../../../src/api-client";

function download(filename: string, content: string, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function TeacherExportsPage() {
  const [classrooms, setClassrooms] = useState<{ classId: string }[]>([]);
  const [classId, setClassId] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (session) void listClassrooms(session.accessToken).then((items) => { setClassrooms(items); setClassId(items[0]?.classId ?? ""); }).catch(() => setStatus("无法读取班级列表。"));
  }, []);

  async function exportCourses() {
    const session = currentSession();
    if (!session) return setStatus("请先登录教师账号。");
    try {
      const courses = await listCourses(session.accessToken);
      download("courses.json", JSON.stringify(courses, null, 2), "application/json");
      setStatus(`已导出 ${courses.length} 门课程。`);
    } catch {
      setStatus("导出课程失败。");
    }
  }

  async function exportReports() {
    const session = currentSession();
    if (!session || !classId) return setStatus("请选择班级。");
    try {
      const students = await listClassroomStudents(session.accessToken, classId);
      const rows = await Promise.all(students.map(async (student) => {
        try {
          const report = await getStudentLearningReport(session.accessToken, student.studentId);
          return [student.studentId, report.completedLessons.length, report.submittedAssignments.length, report.reviewedAssignments.length].join(",");
        } catch {
          return [student.studentId, 0, 0, 0].join(",");
        }
      }));
      download(`${classId}-reports.csv`, ["学生,完成课程,提交作业,已批改", ...rows].join("\n"), "text/csv");
      setStatus(`已导出 ${classId} 的学习报告。`);
    } catch {
      setStatus("导出报告失败。");
    }
  }

  return (
    <main className="teacher-shell">
      <header className="teacher-home-header"><div><p className="student-home__eyebrow">EXPORT</p><h1>课程导出</h1><p>下载课程结构和学生学习报告，方便备份或提交学校。</p></div></header>
      {status && <div className="settings-note">{status}</div>}
      <div className="teacher-card-grid">
        <article className="teacher-card"><span>课程内容</span><h2>导出课程 JSON</h2><p>包含课程块、逐字稿、提示词和学生流程。</p><button className="teacher-primary-link" type="button" onClick={() => void exportCourses()}>下载课程</button></article>
        <article className="teacher-card"><span>学习数据</span><h2>导出学习报告 CSV</h2><p>汇总所选班级每个学生的课程与作业完成情况。</p><div className="teacher-toolbar__actions"><select value={classId} onChange={(event) => setClassId(event.target.value)}>{classrooms.map((item) => <option key={item.classId} value={item.classId}>{item.classId}</option>)}</select><button className="teacher-primary-link" type="button" onClick={() => void exportReports()}>下载报告</button></div></article>
      </div>
    </main>
  );
}
