"use client";

import { useEffect, useMemo, useState } from "react";

import { currentSession, listClassrooms, listCourses, listReviewWorks, type ManagedClassroom } from "../../src/api-client";
import { teacherNavigation } from "../../src/navigation";

export default function TeacherHomePage() {
  const [classrooms, setClassrooms] = useState<ManagedClassroom[]>([]);
  const [courseCount, setCourseCount] = useState(0);
  const [pendingWorks, setPendingWorks] = useState(0);
  const [status, setStatus] = useState("正在读取课堂数据…");

  useEffect(() => {
    const session = currentSession();
    if (!session || !["teacher", "organization_admin", "platform_admin"].includes(session.role)) {
      setStatus("请先使用教师账号登录，查看你的课堂与课程。");
      return;
    }
    void Promise.all([
      listClassrooms(session.accessToken),
      listCourses(session.accessToken),
      listReviewWorks(session.accessToken, { reviewState: "pending" }),
    ]).then(([nextClassrooms, courses, works]) => {
      setClassrooms(nextClassrooms);
      setCourseCount(courses.length);
      setPendingWorks(works.length);
      setStatus("");
    }).catch(() => setStatus("课堂数据暂时无法读取，请确认服务连接和登录状态。"));
  }, []);

  const openClassrooms = useMemo(() => classrooms.filter((item) => item.state === "open"), [classrooms]);
  const onlineStudents = useMemo(() => classrooms.reduce((total, item) => total + item.onlineStudents, 0), [classrooms]);
  const helpNeeded = useMemo(() => classrooms.reduce((total, item) => total + item.helpNeeded, 0), [classrooms]);

  return <main className="teacher-shell"><header className="teacher-home-header"><div><p className="student-home__eyebrow">TEACHER WORKBENCH</p><h1>今天的课堂</h1><p>从这里查看真实课堂状态、课程和待审核作品。</p></div><a className="teacher-primary-link" href="/teacher/classroom">进入实时课堂 →</a></header>{status && <div className="settings-note">{status}</div>}<div className="teacher-overview-grid"><article><span>正在进行</span><strong>{openClassrooms.length} 个课堂</strong><p>{onlineStudents} 名学生在线 · {helpNeeded} 人需要帮助</p></article><article><span>待审核</span><strong>{pendingWorks} 个作品</strong><p>审核通过后可进入学生作品展示墙</p></article><article><span>已建课程</span><strong>{courseCount} 门</strong><p>可继续编辑、发布或导出课程资料</p></article></div><div className="teacher-next-actions"><a href="/teacher/review" className={pendingWorks ? "is-attention" : "is-ready"}><strong>{pendingWorks}</strong><span><b>待审核作品</b><small>{pendingWorks ? "进入审核队列" : "当前没有待审核作品"}</small></span>→</a><a href="/teacher/classroom" className={helpNeeded ? "is-attention" : "is-ready"}><strong>{helpNeeded}</strong><span><b>需要帮助的学生</b><small>{helpNeeded ? "进入实时课堂查看" : "当前没有求助"}</small></span>→</a><a href="/teacher/courses" className="is-ready"><strong>{courseCount}</strong><span><b>课程资源</b><small>继续编辑或发布课程</small></span>→</a></div><div className="backoffice-nav-grid">{teacherNavigation.map((item) => <a href={item.href} key={item.id}><span>{item.icon}</span><div><strong>{item.label}</strong><p>{item.description}</p></div></a>)}</div></main>;
}
