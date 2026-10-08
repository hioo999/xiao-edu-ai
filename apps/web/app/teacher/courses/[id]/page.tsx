"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import {
  CourseMaterial,
  currentSession,
  deleteCourseMaterial,
  getCourse,
  listCourseMaterials,
  listCourseLearningProgress,
  listCourseHomework,
  annotateHomework,
  HomeworkSubmission,
  LearningProgress,
  ManagedCourse,
  publishCourse,
  saveCourse,
  unpublishCourse,
  deleteCourse,
  uploadCourseMaterial,
} from "../../../../src/api-client";

const blankCourse = (courseId: string): ManagedCourse => ({ courseId, title: "", summary: "", blocks: [], teacherScript: "", promptExamples: [], studentFlow: [], published: false });

export default function TeacherCourseDetailPage() {
  const params = useParams<{ id: string }>();
  const routeId = params.id;
  const courseId = routeId === "new" ? "" : routeId;
  const uploadRef = useRef<HTMLInputElement>(null);
  const [course, setCourse] = useState<ManagedCourse>(blankCourse(courseId));
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [classId, setClassId] = useState("class-001");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState<LearningProgress[]>([]);
  const [submissions, setSubmissions] = useState<HomeworkSubmission[]>([]);
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<string, string>>({});

  const resolvedId = course.courseId;
  const refreshMaterials = async (id: string) => {
    const session = currentSession();
    if (session && id) setMaterials(await listCourseMaterials(session.accessToken, id));
  };

  useEffect(() => {
    const session = currentSession();
    if (!session || !courseId) return;
    void getCourse(session.accessToken, courseId).then((item) => {
      setCourse(item);
      return refreshMaterials(item.courseId);
    }).catch(() => setStatus("未找到服务端课程，可重新保存为新课程。"));
  }, [courseId]);

  useEffect(() => {
    const session = currentSession();
    if (!session || !resolvedId || !course.published) return;
    void Promise.all([listCourseLearningProgress(session.accessToken, resolvedId), listCourseHomework(session.accessToken, resolvedId)]).then(([nextProgress, nextSubmissions]) => {
      setProgress(nextProgress);
      setSubmissions(nextSubmissions);
    }).catch(() => setStatus("学习进度读取失败。"));
  }, [resolvedId, course.published]);

  function updateList(field: "studentFlow" | "promptExamples", value: string) {
    setCourse({ ...course, [field]: value.split("\n").map((item) => item.trim()).filter(Boolean) });
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    const session = currentSession();
    const nextId = resolvedId || `course-${Date.now()}`;
    if (!session || !course.title.trim()) return setStatus("请先填写课程标题并登录教师账号。");
    try {
      const saved = await saveCourse(session.accessToken, { ...course, courseId: nextId, title: course.title.trim() });
      setCourse(saved);
      setStatus("课程内容已保存。");
      if (routeId === "new") window.history.replaceState(null, "", `/teacher/courses/${saved.courseId}`);
    } catch { setStatus("课程保存失败。"); }
  }

  async function upload(file: File | undefined) {
    const session = currentSession();
    if (!file || !session || !resolvedId) return setStatus("请先保存课程，再上传课件资源。");
    try {
      await uploadCourseMaterial(session.accessToken, resolvedId, file);
      await refreshMaterials(resolvedId);
      setStatus("课件资源已上传。");
    } catch { setStatus("课件上传失败。"); }
  }

  async function removeMaterial(material: CourseMaterial) {
    const session = currentSession();
    if (!session || !window.confirm(`确定删除“${material.filename}”吗？`)) return;
    try {
      await deleteCourseMaterial(session.accessToken, material.materialId);
      await refreshMaterials(resolvedId);
    } catch { setStatus("删除课件失败。"); }
  }

  async function publish() {
    const session = currentSession();
    if (!session || !resolvedId || !classId.trim()) return setStatus("请先保存课程并填写班级编号。");
    try {
      if (!course.published) {
        const saved = await saveCourse(session.accessToken, { ...course, published: true });
        setCourse(saved);
      }
      await publishCourse(session.accessToken, resolvedId, classId.trim());
      setStatus(`课程已发布到 ${classId}。`);
    } catch { setStatus("课程发布失败。"); }
  }

  async function unpublish() {
    const session = currentSession();
    if (!session || !resolvedId || !classId.trim()) return setStatus("请填写要撤回的班级编号。");
    try {
      await unpublishCourse(session.accessToken, resolvedId, classId.trim());
      setStatus(`已从 ${classId} 撤回课程发布。`);
    } catch { setStatus("撤回发布失败。"); }
  }

  async function removeCourse() {
    const session = currentSession();
    if (!session || !resolvedId || !window.confirm("确定删除这节课程及其班级发布关系吗？")) return;
    try {
      await deleteCourse(session.accessToken, resolvedId);
      window.location.assign("/teacher/courses");
    } catch { setStatus("课程删除失败。"); }
  }

  async function annotate(submission: HomeworkSubmission, feedback: string) {
    const session = currentSession();
    if (!session) return;
    try {
      const updated = await annotateHomework(session.accessToken, submission.submissionId, feedback.trim(), "reviewed");
      setSubmissions((current) => current.map((item) => item.submissionId === updated.submissionId ? updated : item));
      setFeedbackDrafts((current) => ({ ...current, [submission.submissionId]: "" }));
      setStatus("批注已保存并同步给学生。");
    } catch { setStatus("批注保存失败。"); }
  }

  return (
    <main className="teacher-shell course-editor-page">
      <a href="/teacher/courses" className="workspace-back">← 课程管理</a>
      <header className="course-editor-header"><div><p className="student-home__eyebrow">COURSE EDITOR</p><h1>{course.title || "新建课程"}</h1><p>学生端可见课程步骤与课件；逐字稿、提示词仅教师可见。</p></div><div><button className="teacher-secondary-button" type="button" onClick={() => void unpublish()}>撤回发布</button><button className="teacher-secondary-button" type="button" onClick={() => void publish()}>发布到班级</button><button className="teacher-primary-link" type="button" onClick={() => void save()}>保存课件</button>{resolvedId && <button type="button" onClick={() => void removeCourse()}>删除课程</button>}</div></header>
      <form onSubmit={save} className="course-editor-grid">
        <aside className="course-editor-steps"><strong>课程流程</strong><label>课程标题<input value={course.title} onChange={(event) => setCourse({ ...course, title: event.target.value })} placeholder="例如：我的第一个 AI 网页" required /></label><label>学生步骤（每行一项）<textarea value={course.studentFlow.join("\n")} onChange={(event) => updateList("studentFlow", event.target.value)} placeholder="观察案例&#10;说出创作想法&#10;输入提示词并迭代" /></label><label>发布班级<input value={classId} onChange={(event) => setClassId(event.target.value)} /></label></aside>
        <section className="course-material-editor"><div className="course-material-toolbar"><strong>学生课程内容</strong><span className="status-pill">{course.published ? "已发布" : "草稿"}</span></div><label>课程简介<textarea value={course.summary} onChange={(event) => setCourse({ ...course, summary: event.target.value })} placeholder="向学生解释这节课的目标。" /></label><label>教学内容（每行会成为一个阅读步骤）<textarea value={course.blocks.map((block) => block.content).join("\n")} onChange={(event) => setCourse({ ...course, blocks: event.target.value.split("\n").map((content) => content.trim()).filter(Boolean).map((content) => ({ kind: "step", content, authoredBy: "teacher" })) })} placeholder="先观察示例，再用自己的话说出你想做的作品。" /></label><div className="course-resource-box"><div><strong>课件资源</strong><p>可上传课件、图片、课堂视频和参考资料。</p></div><input ref={uploadRef} type="file" hidden onChange={(event) => void upload(event.target.files?.[0])} /><button type="button" onClick={() => uploadRef.current?.click()}>＋ 上传资源</button></div><div className="course-resource-list">{materials.map((material) => <span key={material.materialId}>📄 {material.filename}<button type="button" onClick={() => void removeMaterial(material)}>删除</button></span>)}{materials.length === 0 && <span>还没有上传课件资源</span>}</div></section>
        <aside className="teacher-script-panel"><div className="script-tabs"><strong>教师备课资料</strong><span>仅教师可见</span></div><section><h2>逐字稿</h2><textarea value={course.teacherScript} onChange={(event) => setCourse({ ...course, teacherScript: event.target.value })} placeholder="写下课堂开场、引导提问和总结话术。" /></section><section><h2>提示词示例（每行一个）</h2><textarea value={course.promptExamples.join("\n")} onChange={(event) => updateList("promptExamples", event.target.value)} placeholder="帮我设计一个海洋环保主题网页&#10;把颜色改得更明亮" /></section></aside>
      </form>
      {resolvedId && course.published && <section className="teacher-learning-dashboard"><div className="course-material-toolbar"><strong>学习进度与作业</strong><span>{progress.filter((item) => item.completed).length} 人完成 · {submissions.length} 份作业</span></div><div className="learning-dashboard-grid"><div><h2>学习进度</h2>{progress.length === 0 ? <p>还没有学生学习这门课。</p> : <ul>{progress.map((item) => <li key={`${item.studentId}-${item.courseId}`}><b>{item.studentId}</b><span>{item.percent}%{item.completed ? " · 已完成" : ""}</span></li>)}</ul>}</div><div><h2>作业批改</h2>{submissions.length === 0 ? <p>还没有学生提交作业。</p> : <ul>{submissions.map((submission) => <li key={submission.submissionId}><b>{submission.studentId}</b><span>{submission.status === "reviewed" ? "已批改" : "待批改"}</span><p>{submission.content}</p><textarea value={feedbackDrafts[submission.submissionId] ?? ""} onChange={(event) => setFeedbackDrafts((current) => ({ ...current, [submission.submissionId]: event.target.value }))} placeholder="输入给学生的批注…" />{submission.teacherFeedback && <em>已有批注：{submission.teacherFeedback}</em>}<button type="button" onClick={() => void annotate(submission, feedbackDrafts[submission.submissionId] ?? "")}>保存批注</button></li>)}</ul>}</div></div></section>}
      {status && <div className="admin-feedback">{status}</div>}
    </main>
  );
}
