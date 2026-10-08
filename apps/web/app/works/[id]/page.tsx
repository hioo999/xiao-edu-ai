"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { commentOnWork, CreativeWork, createShare, currentSession, getWork, getWorkInteractions, likeWork, resolveWorkMediaUrl, WorkComment } from "../../../src/api-client";
const workspaces: Record<string, string> = { webpage: "html", image: "image", music: "music", video: "video", text: "chat" };
function WorkPreview({ work, html }: { work: CreativeWork; html: string | null }) {
  const cover = work.coverUrl || work.previewUrl;
  if (work.kind === "image" && cover) return <img className="work-detail__media" src={resolveWorkMediaUrl(cover)} alt={`${work.title}作品预览`} />;
  if (work.kind === "video" && work.previewUrl) return <video className="work-detail__media" controls src={resolveWorkMediaUrl(work.previewUrl)}>你的浏览器暂不支持视频播放。</video>;
  if (work.kind === "music" && work.previewUrl) return <div className="work-detail__audio"><span>♫</span><audio controls src={resolveWorkMediaUrl(work.previewUrl)}>你的浏览器暂不支持音频播放。</audio></div>;
  if (work.kind === "webpage" && work.previewUrl) return <iframe className="work-detail__iframe" title={`${work.title}在线预览`} sandbox="allow-forms allow-modals allow-popups allow-scripts" src={work.previewUrl} />;
  if (work.kind === "webpage" && html) return <iframe className="work-detail__iframe" title={`${work.title}预览`} sandbox="allow-scripts allow-same-origin" srcDoc={html} />;
  return <div className="work-detail__cover" style={{ background: "linear-gradient(145deg, #7e8df5, #55d7e8 55%, #fff0a8)" }}><span>{work.kind}</span><strong>{work.kind === "webpage" ? "⌘" : work.kind === "image" ? "◉" : work.kind === "music" ? "♫" : "▶"}</strong><small>作品预览</small></div>;
}
export default function WorkDetailPage() {
  const params = useParams<{ id: string }>();
  const [work, setWork] = useState<CreativeWork | null>(null);
  const [html, setHtml] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [comments, setComments] = useState<WorkComment[]>([]);
  const [likeCount, setLikeCount] = useState(0);
  const [liked, setLiked] = useState(false);
  const [commentBody, setCommentBody] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const session = currentSession();
    if (session && params.id) {
      void getWork(session.accessToken, params.id).then(setWork).catch(() => setMessage("无法读取作品详情。"));
      void getWorkInteractions(session.accessToken, params.id).then((data) => { setComments(data.comments); setLikeCount(data.likeCount); setLiked(data.liked); }).catch(() => {});
    }
  }, [params.id]);

  useEffect(() => {
    const session = currentSession();
    if (!session || !params.id || work?.kind !== "webpage") return;
    void fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/works/${params.id}/download`, { headers: { Authorization: `Bearer ${session.accessToken}` } })
      .then((response) => response.ok && response.headers.get("content-type")?.includes("text/html") ? response.text() : null)
      .then(setHtml).catch(() => setHtml(null));
  }, [work, params.id]);

  async function share() { const session = currentSession(); if (!session || !work) return; try { const result = await createShare(session.accessToken, work.assetId); const shareUrl = `${window.location.origin}/share/${result.token}`; await navigator.clipboard?.writeText(shareUrl); setMessage(`分享链接已复制，有效至 ${new Date(result.expiresAt).toLocaleString()}。`); } catch (error) { setMessage(error instanceof Error ? error.message : "作品暂不能分享，请先等待老师审核通过。"); } }
  async function toggleLike() { const session = currentSession(); if (!session || !work) return; try { const data = await likeWork(session.accessToken, work.assetId, !liked); setLiked(data.liked); setLikeCount(data.likeCount); } catch (error) { setMessage(error instanceof Error ? error.message : "点赞失败。"); } }
  async function submitComment() { const session = currentSession(); if (!session || !work || !commentBody.trim()) return; setBusy(true); try { const comment = await commentOnWork(session.accessToken, work.assetId, commentBody); setComments((items) => [...items, comment]); setCommentBody(""); } catch (error) { setMessage(error instanceof Error ? error.message : "点评发送失败。"); } finally { setBusy(false); } }
  async function downloadUpload() { const session = currentSession(); if (!session || !work) return; const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/works/${work.assetId}/download`, { headers: { Authorization: `Bearer ${session.accessToken}` } }); if (!response.ok) return setMessage("这件作品没有可下载的上传文件。"); const blobUrl = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = blobUrl; link.download = work.title; link.click(); URL.revokeObjectURL(blobUrl); }
  if (!work) return <main className="catalog-shell"><a href="/projects" className="workspace-back">← 我的作品</a><h1>{message || "正在读取作品..."}</h1></main>;
  const workspace = workspaces[work.kind] ?? "chat";
  const canComment = ["teacher", "organization_admin", "platform_admin"].includes(currentSession()?.role ?? "");
  const createRoute = `/workspace/${workspace}?prompt=${encodeURIComponent(work.prompt || `参考《${work.title}》的灵感，帮我做一个适合小学生的新作品`)}`;
  const steps = work.processSteps.length ? work.processSteps : [`选定主题：${work.title}`, "把自己的想法告诉 AI，并补充画面、角色或故事细节。", "预览作品，修改成自己最喜欢的样子。"];
  return <main className="work-detail-page"><a href="/showcase" className="work-detail-page__back">← 作品展示墙</a><div className="work-detail-page__layout"><section className="work-detail__preview"><WorkPreview work={work} html={html} /><div className="work-detail__preview-bar"><span>{work.reviewState === "approved" ? "审核已通过" : "等待老师审核"}</span><button type="button" onClick={() => void toggleLike()}>{liked ? "❤ 已点赞" : "♡ 点赞"} {likeCount}</button><button type="button" onClick={() => void share()}>分享作品</button>{work.previewUrl && <a href={work.previewUrl} download>下载作品</a>}<button type="button" onClick={() => void downloadUpload()}>下载上传文件</button></div></section><article className="work-detail__content"><div className="work-detail__eyebrow">{work.kind}作品 · 小小创造家</div><h1>{work.title}</h1><p className="work-detail__student">✦ 小小创作者 · 适合 {work.gradeMin}-{work.gradeMax} 年级</p><p className="work-detail__description">这是我用 AI 完成的创作作品。</p><section><h2>我是怎样做出来的？</h2><ol className="work-detail__steps">{steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol></section><section><h2>我的创作小提示</h2><div className="work-detail__prompt">{work.prompt || "继续用自己的想法完善作品。"}</div></section><section><h2>老师点评</h2><div className="work-comment-list">{comments.length === 0 ? <p className="work-comment-empty">老师点评会出现在这里；喜欢这件作品可以点一颗小心心。</p> : comments.map((comment) => <div className="work-comment" key={comment.commentId}><span className="work-comment__teacher">老师点评 · {new Date(comment.createdAt).toLocaleString()}</span><p>{comment.body}</p></div>)}</div>{canComment && <div className="work-comment-form"><input value={commentBody} onChange={(event) => setCommentBody(event.target.value)} placeholder="写下给学生的鼓励与建议…" maxLength={2000} /><button type="button" disabled={busy} onClick={() => void submitComment()}>{busy ? "发送中…" : "发布点评"}</button></div>}</section>{message && <div className="settings-note">{message}</div>}<div className="work-detail__actions"><a href={createRoute}>用这个灵感创作</a><a href="/">继续逛逛</a></div></article></div></main>;
}
