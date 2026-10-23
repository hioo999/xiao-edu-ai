"use client";

import { useEffect, useState } from "react";

import { currentSession, LearningReport, myLearningReport } from "../../../src/api-client";

export default function StudentReportsPage() {
  const [report, setReport] = useState<LearningReport | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (!session) { setMessage("登录后即可查看自己的成长报告。"); return; }
    void myLearningReport(session.accessToken).then(setReport).catch(() => setMessage("成长报告还没有生成：完成课程、提交作业后会自动出现在这里。"));
  }, []);

  return (
    <main className="catalog-shell student-report-page">
      <a href="/" className="workspace-back">← 创作大厅</a>
      <p className="student-home__eyebrow">MY GROWTH</p>
      <h1>我的成长报告</h1>
      {message && <div className="settings-note">{message}</div>}
      {report && <div className="report-highlight"><strong>本周学习小结</strong><span>你的每一次课程和作业都会被记录，并标注为 AI 辅助创作。</span></div>}
      {report && <div className="teacher-card-grid">
        <article className="teacher-card"><span>完成课程</span><h2>{report.completedLessons.length} 节</h2><p>{report.completedLessons.length ? report.completedLessons.join("、") : "从第一节课开始吧。"}</p></article>
        <article className="teacher-card"><span>提交作业</span><h2>{report.submittedAssignments.length} 次</h2><p>{report.submittedAssignments.length ? report.submittedAssignments.join("、") : "完成课程后提交作品。"}</p></article>
        <article className="teacher-card"><span>已批改</span><h2>{report.reviewedAssignments.length} 次</h2><p>{report.reviewedAssignments.length ? report.reviewedAssignments.join("、") : "等待老师批改反馈。"}</p></article>
        <article className="teacher-card"><span>AI 辅助</span><h2>{report.aiGenerated ? "已标注" : "未标注"}</h2><p>平台会如实标记 AI 生成内容，帮助你了解自己的创作过程。</p></article>
      </div>}
    </main>
  );
}
