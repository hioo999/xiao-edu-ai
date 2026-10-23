"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import { AuditRecord, currentSession, exportAuditRecords, listAuditRecords, platformReadiness } from "../../../src/api-client";

export default function AuditPage() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [status, setStatus] = useState("正在检查平台运行状态…");

  useEffect(() => {
    void platformReadiness().then(() => setStatus("平台存储运行正常，自动备份每天执行一次。"))
      .catch((error) => setStatus(error instanceof Error ? error.message : "平台存储检查失败"));
    const session = currentSession();
    if (session) void listAuditRecords(session.accessToken).then(setRecords).catch(() => setStatus("平台状态正常，但暂时无法读取审计记录。"));
  }, []);

  async function exportRecords() {
    const session = currentSession();
    if (!session) return setStatus("请先登录管理员账号。");
    try {
      const blob = await exportAuditRecords(session.accessToken);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "audit-records.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch { setStatus("导出审计记录失败。"); }
  }

  return <AdminShell active="/admin/audit"><AdminPageLayout eyebrow="SECURITY & OPERATIONS" title="安全与审计" description="查看平台存储状态、管理员操作记录与备份保护策略。" actions={<button className="admin-primary-button" type="button" onClick={() => void exportRecords()}>导出 CSV</button>}><AdminSection title="运行保障" description="SQLite、课件与生成作品共用持久化数据卷。" toolbar={<span className="status-chip status-chip--good">● 已启用每日备份</span>}><div className="settings-note">{status}</div></AdminSection><AdminSection title="管理员操作记录" description="模型配置、权限和关键资源修改都会显示在这里。"><div className="admin-log-table"><div className="admin-log-head"><span>时间</span><span>操作者</span><span>操作</span><span>对象</span></div>{records.length ? records.map((record) => <div key={record.record_id}><span>{new Date(record.created_at).toLocaleString()}</span><span>{record.actor_id}</span><span>{record.action}</span><span>{record.target_type} · {record.target_id}</span></div>) : <div><span>暂无记录</span><span>—</span><span>—</span><span>—</span></div>}</div></AdminSection></AdminPageLayout></AdminShell>;
}
