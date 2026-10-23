"use client";

import { useEffect, useState } from "react";
import {
  addKnowledge,
  currentSession,
  deleteKnowledge,
  deleteManagedTool,
  KnowledgeDocument,
  listKnowledge,
  listManagedTools,
  ManagedTool,
  saveManagedTool,
} from "../../../src/api-client";
import { AdminPageLayout, AdminSection } from "./admin-page-layout";

export function KnowledgeManager() {
  const [items, setItems] = useState<KnowledgeDocument[]>([]);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");

  const refresh = async () => {
    const session = currentSession();
    if (session) setItems(await listKnowledge(session.accessToken));
  };

  useEffect(() => { void refresh().catch(() => setMessage("暂无知识库内容。")); }, []);

  async function save() {
    const session = currentSession();
    if (!session || !title.trim()) return;
    try {
      await addKnowledge(session.accessToken, title.trim());
      setTitle("");
      await refresh();
      setMessage("知识条目已保存。");
    } catch {
      setMessage("知识条目保存失败。");
    }
  }

  async function remove(item: KnowledgeDocument) {
    const session = currentSession();
    if (!session || !window.confirm(`确定删除“${item.title}”吗？`)) return;
    try {
      await deleteKnowledge(session.accessToken, item.document_id);
      await refresh();
      setMessage("知识条目已删除。");
    } catch {
      setMessage("删除失败，请确认权限后重试。");
    }
  }

  return (
    <Manager title="知识库" subtitle="管理课程、机构和平台可授权给智能体的学习资料。" message={message}>
      <div className="settings-form">
        <label>知识条目标题<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：小学网页创作教学规范" /></label>
        <button className="admin-primary-button" type="button" onClick={() => void save()}>保存知识条目</button>
      </div>
      <Table
        headers={["标题", "范围", "范围 ID", "操作"]}
        rows={items.map((item) => [item.title, item.scope, item.scope_id, <button key={item.document_id} type="button" onClick={() => void remove(item)}>删除</button>])}
      />
    </Manager>
  );
}

export function ToolManager({ kind, title }: { kind: "skills" | "mcp"; title: string }) {
  const [items, setItems] = useState<ManagedTool[]>([]);
  const [name, setName] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [instruction, setInstruction] = useState("");
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [editingEnabled, setEditingEnabled] = useState(true);
  const [message, setMessage] = useState("");

  const refresh = async () => {
    const session = currentSession();
    if (session) setItems(await listManagedTools(session.accessToken, kind));
  };

  useEffect(() => { void refresh().catch(() => setMessage("暂无已保存配置。")); }, [kind]);

  async function save() {
    const session = currentSession();
    if (!session || !name.trim()) return;
    try {
      const isEditing = Boolean(editingToolId);
      await saveManagedTool(session.accessToken, kind, {
        toolId: editingToolId ?? `${kind}-${Date.now()}`,
        name: name.trim(),
        capabilities: capabilities.trim(),
        enabled: editingToolId ? editingEnabled : true,
        instruction: instruction.trim(),
      });
      resetForm();
      await refresh();
      setMessage(isEditing ? "配置已更新。" : "配置已保存并启用。");
    } catch {
      setMessage("配置保存失败。");
    }
  }

  function resetForm() {
    setName("");
    setCapabilities("");
    setInstruction("");
    setEditingToolId(null);
    setEditingEnabled(true);
  }

  function startEdit(item: ManagedTool) {
    setName(item.name);
    setCapabilities(item.capabilities);
    setInstruction(item.instruction);
    setEditingToolId(item.tool_id);
    setEditingEnabled(item.enabled);
    setMessage(`正在编辑“${item.name}”。`);
  }

  async function toggle(item: ManagedTool) {
    const session = currentSession();
    if (!session) return;
    try {
      await saveManagedTool(session.accessToken, kind, { toolId: item.tool_id, name: item.name, capabilities: item.capabilities, enabled: !item.enabled, instruction: item.instruction });
      await refresh();
    } catch {
      setMessage("更新工具状态失败。");
    }
  }

  async function remove(item: ManagedTool) {
    const session = currentSession();
    if (!session || !window.confirm(`确定删除“${item.name}”吗？`)) return;
    try {
      await deleteManagedTool(session.accessToken, kind, item.tool_id);
      await refresh();
      setMessage("工具配置已删除。");
    } catch {
      setMessage("删除工具配置失败。");
    }
  }

  return (
    <Manager title={title} subtitle={kind === "skills" ? "定义智能体可使用的教学能力和安全范围。" : "仅配置经过审核的 MCP 服务与工具能力。"} message={message}>
      <div className="settings-form">
        <label>名称<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
        <label>{kind === "skills" ? "适用创作能力" : "允许能力"}<input value={capabilities} onChange={(event) => setCapabilities(event.target.value)} placeholder={kind === "skills" ? "text, html, image, music, video，或 * 表示全部" : "例如：course.read, image.generate"} /></label>
        {kind === "skills" && <label>教学规则<textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} maxLength={8000} placeholder="例如：先用一句鼓励回应学生；再给出不超过 3 个清晰的下一步。" /></label>}
        <button className="admin-primary-button" type="button" onClick={() => void save()}>{editingToolId ? "保存修改" : "保存并启用"}</button>
        {editingToolId && <button type="button" onClick={resetForm}>取消编辑</button>}
      </div>
      <Table
        headers={kind === "skills" ? ["名称", "允许能力", "教学规则", "状态", "操作"] : ["名称", "允许能力", "状态", "操作"]}
        rows={items.map((item) => [
          item.name,
          item.capabilities || "未配置",
          ...(kind === "skills" ? [item.instruction || "未配置"] : []),
          item.enabled ? "已启用" : "已停用",
          <span key={item.tool_id}>{kind === "skills" && <button type="button" onClick={() => startEdit(item)}>编辑</button>}<button type="button" onClick={() => void toggle(item)}>{item.enabled ? "停用" : "启用"}</button><button type="button" onClick={() => void remove(item)}>删除</button></span>,
        ])}
      />
    </Manager>
  );
}

function Manager({ title, subtitle, message, children }: { title: string; subtitle: string; message: string; children: React.ReactNode }) {
  return <AdminPageLayout eyebrow="AI GOVERNANCE" title={title} description={subtitle}><AdminSection title="配置与清单" description="先配置能力边界，再启用给学生使用。">{message && <div className="admin-feedback">{message}</div>}{children}</AdminSection></AdminPageLayout>;
}

function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return <div className="admin-log-table"><div className="admin-log-head">{headers.map((header) => <span key={header}>{header}</span>)}</div>{rows.map((row, index) => <div key={index}>{row.map((cell, cellIndex) => <span key={cellIndex}>{cell}</span>)}</div>)}</div>;
}
