"use client";

import { useEffect, useState } from "react";

import { CourseMaterial, HomeworkSubmission, LearningProgress, ManagedCourse, courseMaterialDownloadUrl, currentSession, currentUser, listMyHomework, listMyLearningProgress, listStudentCourseMaterials, listStudentCourses, submitHomework, upsertLearningProgress } from "../../src/api-client";

function practiceRoute(course: ManagedCourse, stepIndex: number): string {
  const block = course.blocks[stepIndex];
  const workspace = block?.kind === "video" ? "video" : block?.kind === "image" ? "image" : block?.kind === "text" ? "chat" : "html";
  const prompt = course.promptExamples[stepIndex] ?? course.promptExamples[0] ?? "";
  return `/workspace/${workspace}${prompt ? `?prompt=${encodeURIComponent(prompt)}` : ""}`;
}

export default function CoursesPage() {
  const [courses, setCourses] = useState<ManagedCourse[]>([]);
  const [materials, setMaterials] = useState<Record<string, CourseMaterial[]>>({});
  const [openCourse, setOpenCourse] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [progressByCourse, setProgressByCourse] = useState<Record<string, LearningProgress>>({});
  const [homeworkByCourse, setHomeworkByCourse] = useState<Record<string, HomeworkSubmission[]>>({});
  const [homeworkDraft, setHomeworkDraft] = useState("");
  const [message, setMessage] = useState("正在读取老师发布的课程…");

  useEffect(() => {
    const session = currentSession();
    if (!session || session.role !== "student") {
      setMessage("请先使用学生账号登录后查看课程。");
      return;
    }
    void currentUser(session.accessToken).then(async (user) => {
      if (!user.classId) throw new Error("老师还没有为你分配班级。");
      const published = await listStudentCourses(session.accessToken, user.classId);
      setCourses(published);
      const [progress, homework] = await Promise.all([listMyLearningProgress(session.accessToken), listMyHomework(session.accessToken)]);
      setProgressByCourse(Object.fromEntries(progress.map((item) => [item.courseId, item])));
      setHomeworkByCourse(homework.reduce<Record<string, HomeworkSubmission[]>>((result, item) => ({ ...result, [item.courseId]: [...(result[item.courseId] ?? []), item] }), {}));
      setMessage(published.length ? "" : "老师暂时还没有发布课程，稍后再来看看。");
    }).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "课程加载失败。"));
  }, []);

  async function toggleCourse(course: ManagedCourse) {
    const session = currentSession();
    if (!session) return;
    if (openCourse === course.courseId) return setOpenCourse(null);
    try {
      const user = await currentUser(session.accessToken);
      if (!user.classId) throw new Error("没有可用班级。");
      const nextMaterials = await listStudentCourseMaterials(session.accessToken, user.classId, course.courseId);
      setMaterials((current) => ({ ...current, [course.courseId]: nextMaterials }));
      setOpenCourse(course.courseId);
      setCurrentStep(0);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "课程资源加载失败。");
    }
  }

  async function markCourseComplete(course: ManagedCourse) {
    const session = currentSession();
    if (!session) return;
    try {
      const total = course.studentFlow.length || course.blocks.length || 1;
      const progress = await upsertLearningProgress(session.accessToken, course.courseId, { percent: 100, completed: true, lastBlockIndex: total - 1 });
      setProgressByCourse((current) => ({ ...current, [course.courseId]: progress }));
      setMessage(`已记录“${course.title}”的学习完成。`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "完成进度保存失败。"); }
  }

  async function sendHomework(course: ManagedCourse) {
    const session = currentSession();
    if (!session || !homeworkDraft.trim()) return;
    try {
      const submission = await submitHomework(session.accessToken, course.courseId, homeworkDraft.trim());
      setHomeworkByCourse((current) => ({ ...current, [course.courseId]: [submission, ...(current[course.courseId] ?? [])] }));
      setHomeworkDraft("");
      setMessage("作业已提交，老师批改后会在这里看到反馈。");
    } catch (error) { setMessage(error instanceof Error ? error.message : "作业提交失败。"); }
  }

  return <main className="catalog-shell"><header className="catalog-header"><a href="/" className="workspace-back">← 创作大厅</a><p className="student-home__eyebrow">MY COURSES</p><h1>我的课程</h1><p>跟着老师的步骤学习，不只是得到结果，还要知道为什么这样做。</p></header>{message && <p className="course-upload-status">{message}</p>}{courses.length === 0 && !message.includes("正在读取") ? <section className="student-empty-state"><span>📚</span><h2>这里会出现老师发布给你的课程</h2><p>请用老师分配的学生账号登录。老师发布课程并分配到你的班级后，会自动显示在这里。</p><a className="teacher-primary-link" href="/login">学生登录</a></section> : <div className="course-grid">{courses.map((course, index) => <article className={`course-card course-card--${["cyan", "violet", "amber"][index % 3]}`} key={course.courseId}><div className="course-icon">▣</div><span>{course.studentFlow.length || course.blocks.length} 个学习步骤</span><h2>{course.title}</h2><p>{course.summary || "包含老师准备的学习步骤、示例与挑战任务。"}</p><ol>{course.studentFlow.slice(0, 3).map((step) => <li key={step}>{step}</li>)}</ol><button type="button" onClick={() => void toggleCourse(course)}>{openCourse === course.courseId ? "收起课程" : "开始学习"}</button>{openCourse === course.courseId && <section className="course-player"><aside><b>学习步骤</b>{(course.studentFlow.length ? course.studentFlow : course.blocks.map((block) => block.content)).map((step, stepIndex) => <button className={stepIndex === currentStep ? "is-active" : ""} type="button" key={`${step}-${stepIndex}`} onClick={() => setCurrentStep(stepIndex)}><i>{stepIndex + 1}</i>{step}</button>)}</aside><div className="course-player__lesson"><p>第 {currentStep + 1} 步</p><h3>{(course.studentFlow.length ? course.studentFlow : course.blocks.map((block) => block.content))[currentStep] ?? "开始你的创作"}</h3>{course.blocks[currentStep] && <div className="course-player__block"><span>{course.blocks[currentStep].authoredBy === "teacher" ? "老师提示" : "AI 提示"}</span><p>{course.blocks[currentStep].content}</p></div>}{course.promptExamples[currentStep] && <div className="course-player__prompt"><b>可以这样对 AI 说</b><p>{course.promptExamples[currentStep]}</p><button type="button" onClick={() => navigator.clipboard?.writeText(course.promptExamples[currentStep])}>复制提示词</button></div>}<a href={practiceRoute(course, currentStep)} className="teacher-primary-link">去创作实践 →</a><div className="course-progress-box"><b>学习进度</b><span>{progressByCourse[course.courseId]?.completed ? "已完成 ✓" : `${progressByCourse[course.courseId]?.percent ?? 0}%`}</span><button type="button" onClick={() => void markCourseComplete(course)} disabled={progressByCourse[course.courseId]?.completed}>完成本节课</button><b>提交作业</b><textarea value={homeworkDraft} onChange={(event) => setHomeworkDraft(event.target.value)} placeholder="写下你的作品想法或粘贴创作结果说明…" /><button type="button" onClick={() => void sendHomework(course)}>提交作业</button><ul>{(homeworkByCourse[course.courseId] ?? []).map((item) => <li key={item.submissionId}>{item.status === "reviewed" ? "✅ 已批改" : "⏳ 已提交"}：{item.teacherFeedback || "等待老师反馈"}</li>)}</ul></div></div><div className="course-resource-list">{(materials[course.courseId] ?? []).map((material) => <a key={material.materialId} href={courseMaterialDownloadUrl(material.materialId)} download>📄 下载 {material.filename}</a>)}{(materials[course.courseId] ?? []).length === 0 && <span>老师暂时没有上传附件。</span>}</div></section>}</article>)}</div>}</main>;
}
