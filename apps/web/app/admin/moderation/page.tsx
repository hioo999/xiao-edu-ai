"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { checkModerationContent, currentSession, getModerationPolicy, saveModerationPolicy } from "../../../src/api-client";

export default function ModerationAdminPage() {
  const [enabled, setEnabled] = useState(true);
  const [terms, setTerms] = useState("");
  const [testContent, setTestContent] = useState("");
  const [testMode, setTestMode] = useState("classroom");
  const [testResult, setTestResult] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    void getModerationPolicy(session.accessToken)
      .then((policy) => { setEnabled(policy.enabled); setTerms(policy.blockedTerms.join("\n")); })
      .catch(() => setStatus("暂时无法读取安全审核策略。"));
  }, []);

  async function save() {
    const session = currentSession();
    if (!session) return setStatus("请先登录管理员账号。");
    const blockedTerms = terms.split("\n").map((term) => term.trim()).filter(Boolean);
    try {
      const policy = await saveModerationPolicy(session.accessToken, { enabled, blockedTerms });
      setTerms(policy.blockedTerms.join("\n"));
      setStatus("安全审核策略已保存。");
    } catch {
      setStatus("保存安全审核策略失败。");
    }
  }

  async function test() {
    const session = currentSession();
    if (!session || !testContent.trim()) return setTestResult("请输入需要检测的内容。");
    try {
      const result = await checkModerationContent(session.accessToken, testContent, testMode);
      setTestResult(result.decision === "allowed" ? "检测通过：内容允许发布。" : "已拦截：内容命中安全策略。");
    } catch {
      setTestResult("已拦截：内容命中安全策略。");
    }
  }

  return (
    <AdminShell active="/admin/moderation">
      <main className="admin-page">
        <div className="admin-page-heading">
          <div><p className="admin-eyebrow">CONTENT SAFETY</p><h1>安全审核</h1><p>配置敏感词黑名单、审核开关，并在线检测学生创作内容。</p></div>
        </div>

        <section className="admin-panel">
          <div className="admin-panel-heading"><div><h2>审核策略</h2><p>命中黑名单的内容会在生成前被拦截。</p></div><span className={`status-chip ${enabled ? "status-chip--good" : "status-chip--muted"}`}>{enabled ? "● 审核已启用" : "○ 审核已暂停"}</span></div>
          <div className="settings-form">
            <label>审核开关<select value={enabled ? "yes" : "no"} onChange={(event) => setEnabled(event.target.value === "yes")}><option value="yes">启用审核</option><option value="no">暂停审核</option></select></label>
            <label>敏感词黑名单（每行一个）<textarea value={terms} onChange={(event) => setTerms(event.target.value)} placeholder={"危险词\n辱骂词"} rows={8} /></label>
            <button className="admin-primary-button" type="button" onClick={() => void save()}>保存策略</button>
          </div>
          {status && <div className="admin-feedback">{status}</div>}
        </section>

        <section className="admin-panel">
          <div className="admin-panel-heading"><div><h2>内容检测</h2><p>输入一段内容，验证当前策略是否会拦截。</p></div></div>
          <div className="settings-form">
            <label>检测内容<textarea value={testContent} onChange={(event) => setTestContent(event.target.value)} placeholder="输入学生可能提交的提示词或正文" /></label>
            <label>检测模式<select value={testMode} onChange={(event) => setTestMode(event.target.value)}><option value="classroom">课堂模式</option><option value="free_creation">自由创作</option></select></label>
            <button className="admin-primary-button" type="button" onClick={() => void test()}>开始检测</button>
          </div>
          {testResult && <div className={`admin-feedback ${testResult.startsWith("已拦截") ? "admin-feedback--danger" : ""}`}>{testResult}</div>}
        </section>
      </main>
    </AdminShell>
  );
}
