"use client";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { currentSession, parentWorkDetail } from "../../../../src/api-client";
export default function ParentWorkPage() {
  const { id } = useParams<{ id: string }>();
  const studentId = useSearchParams().get("student") ?? "";
  const [work, setWork] = useState<{ title: string; kind: string; content: string } | null>(null);
  const [message, setMessage] = useState("正在读取作品…");
  useEffect(() => { const session = currentSession(); if (!session || session.role !== "parent" || !studentId) { setMessage("请先使用家长账号登录。"); return; } void parentWorkDetail(session.accessToken, studentId, id).then((item) => { setWork(item); setMessage(""); }).catch((error) => setMessage(error instanceof Error ? error.message : "作品暂时无法读取。")); }, [id, studentId]);
  return <main className="parent-page"><div className="parent-works"><a href="/parent">← 返回家长端</a>{work ? <article><p>{work.kind} · 学生作品</p><h1>{work.title}</h1><p style={{ whiteSpace: "pre-wrap" }}>{work.content || "这件作品已由老师审核并分享给家长。"}</p></article> : <p>{message}</p>}</div></main>;
}
