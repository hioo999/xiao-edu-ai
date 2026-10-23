"use client";

import { useEffect, useState } from "react";
import { currentSession, fetchWorkMedia, getMediaJob, getWork, type CreativeWork } from "../../src/api-client";
import type { AgentMessage } from "../../src/creation-api";
import { buildWordDocument, safeDownloadName } from "../../src/creative-text-export";
import { FormattedCreativeText } from "../components/formatted-creative-text";
import { useWorkMediaUrl } from "../components/use-work-media-url";

export function downloadAgentFile(name: string, content: string, type: string) {
  const source = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a"); link.href = source; link.download = name; link.click();
  window.setTimeout(() => URL.revokeObjectURL(source), 1000);
}

function AgentMedia({ jobId }: { jobId: string }) {
  const [work, setWork] = useState<CreativeWork | null>(null);
  const [status, setStatus] = useState("正在读取创作进度…");
  const [attempt, setAttempt] = useState(0);
  const source = useWorkMediaUrl(work?.previewUrl ?? "");
  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let count = 0;
    async function poll() {
      try {
        const result = await getMediaJob(session!.accessToken, jobId);
        if (!active) return;
        if (result.state === "succeeded" && result.assetId) {
          const asset = await getWork(session!.accessToken, result.assetId);
          if (active) { setWork(asset); setStatus("作品已生成并保存。 "); }
          return;
        }
        if (result.state === "failed") { setStatus(result.error || "生成没有完成，积分按平台规则释放。可以重新发出任务。"); return; }
        setStatus("正在创作 · " + result.progress + "%");
        if (++count < 150) timer = setTimeout(() => void poll(), 4000);
        else setStatus("任务仍在运行，可到作品夹查看，或点击刷新进度。");
      } catch { if (active) setStatus("暂时无法读取进度，请点击刷新进度。 "); }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [jobId, attempt]);

  async function download() {
    const session = currentSession();
    if (!work || !session) return;
    try {
      const response = await fetchWorkMedia(work.previewUrl, session.accessToken);
      if (!response.ok) throw new Error();
      const blob = await response.blob(); const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = objectUrl;
      link.download = safeDownloadName(work.title) + (({ image: ".png", music: ".mp3", video: ".mp4" } as Record<string, string>)[work.kind] ?? ""); link.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch { setStatus("下载暂时失败，请到作品详情重试。 "); }
  }

  return <div className="agent-media-result"><p role="status">{status}</p>{work && source && (work.kind === "image" ? <img src={source} alt={work.title} /> : work.kind === "video" ? <video controls autoPlay muted playsInline src={source} onError={() => setStatus("视频暂时无法播放，请刷新或到作品详情查看。 ")} /> : <><audio controls src={source} onError={() => setStatus("歌曲暂时无法播放，请刷新或到作品详情查看。 ")} />{work.lyrics && <details open><summary>歌词</summary><pre>{work.lyrics}</pre></details>}</>)}<div className="agent-answer-actions">{work ? <><button type="button" onClick={() => void download()}>下载作品</button><a href={"/works/" + work.assetId}>查看作品</a></> : <button type="button" onClick={() => setAttempt((value) => value + 1)}>刷新进度</button>}</div></div>;
}

export function AgentResult({ message, name, onStatus }: { message: AgentMessage; name: string; onStatus: (value: string) => void }) {
  async function copy() {
    try { await navigator.clipboard.writeText(message.text); onStatus("回答已复制。 "); }
    catch { onStatus("复制没有完成，请手动选择内容复制。 "); }
  }
  return <><FormattedCreativeText text={message.text} />{message.html && <iframe title="智能体生成的网页" sandbox="allow-scripts" srcDoc={message.html} />}{message.jobId && <AgentMedia jobId={message.jobId} />}<div className="agent-answer-actions"><button type="button" onClick={() => void copy()}>复制回答</button>{message.html ? <button type="button" onClick={() => downloadAgentFile("my-agent-webpage.html", message.html!, "text/html")}>下载网页</button> : !message.jobId && <button type="button" onClick={() => downloadAgentFile(safeDownloadName(name) + ".doc", buildWordDocument(name, message.text), "application/msword;charset=utf-8")}>下载 Word</button>}{message.assetId && <a href={"/works/" + message.assetId}>查看作品</a>}</div></>;
}
