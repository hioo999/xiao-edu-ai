"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import { batchReviewWorks, CreativeWork, currentSession, getOrganizationSettings, OrganizationSettings, reviewWork, saveOrganizationSettings, updateWorkMetadata, uploadWorkMedia } from "../../../src/api-client";
import { listReviewWorks } from "../../../src/api-client";

const defaults: OrganizationSettings = { displayName: "星芽 AI 创作学习平台", studentHomeEnabled: true, maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all", videoDurationSeconds: 5 };

export default function ShowcaseAdminPage() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [settings, setSettings] = useState<OrganizationSettings>(defaults);
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState<CreativeWork | null>(null);

  const refreshWorks = async () => {
    const session = currentSession();
    if (session) setWorks(await listReviewWorks(session.accessToken));
  };

  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    void Promise.all([refreshWorks(), getOrganizationSettings(session.accessToken)]).then(([, nextSettings]) => setSettings(nextSettings)).catch(() => setStatus("暂时无法读取展示配置或作品。"));
  }, []);

  async function saveRules() {
    const session = currentSession();
    if (!session) return;
    try {
      setSettings(await saveOrganizationSettings(session.accessToken, settings));
      setStatus("首页展示规则已保存。");
    } catch { setStatus("展示规则保存失败。"); }
  }

  async function review(assetId: string, state: "approved" | "rejected", featured: boolean) {
    const session = currentSession();
    if (!session) return setStatus("请先使用教师或管理员账号登录。");
    try {
      const saved = await reviewWork(session.accessToken, assetId, state, featured);
      setWorks((items) => items.map((work) => work.assetId === assetId ? saved : work));
    } catch (error) { setStatus(error instanceof Error ? error.message : "审核失败。"); }
  }

  async function batchReview(state: "approved" | "rejected", featured: boolean) {
    const session = currentSession();
    if (!session || selected.length === 0) return setStatus("请先勾选要审核的作品。");
    try {
      const result = await batchReviewWorks(session.accessToken, selected, state, featured);
      const changed = new Map(result.works.map((work) => [work.assetId, work]));
      setWorks((items) => items.map((work) => changed.get(work.assetId) ?? work));
      setSelected([]);
      setStatus(`已批量${state === "approved" ? "通过" : "退回"} ${result.reviewed} 件作品。`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "批量审核失败。"); }
  }

  function toggleSelected(assetId: string) {
    setSelected((items) => items.includes(assetId) ? items.filter((id) => id !== assetId) : [...items, assetId]);
  }

  async function saveMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const session = currentSession();
    if (!session || !editing) return;
    const form = new FormData(event.currentTarget);
    try {
      let saved = await updateWorkMetadata(session.accessToken, editing.assetId, {
        title: String(form.get("title") ?? ""),
        previewUrl: String(form.get("previewUrl") ?? ""),
        coverUrl: String(form.get("coverUrl") ?? ""),
        processSteps: String(form.get("steps") ?? "").split("\n").map((step) => step.trim()).filter(Boolean),
        gradeMin: Number(form.get("gradeMin")), gradeMax: Number(form.get("gradeMax")),
        visibility: String(form.get("visibility")) as "organization" | "private",
        isExample: form.get("isExample") === "on",
      });
      const coverFile = form.get("coverFile");
      const previewFile = form.get("previewFile");
      if (coverFile instanceof File && coverFile.size > 0) saved = (await uploadWorkMedia(session.accessToken, editing.assetId, "cover", coverFile)).work;
      if (previewFile instanceof File && previewFile.size > 0) saved = (await uploadWorkMedia(session.accessToken, editing.assetId, "preview", previewFile)).work;
      setWorks((items) => items.map((work) => work.assetId === saved.assetId ? saved : work));
      setEditing(null);
      setStatus("作品资料已保存，学生端会立即按新信息展示。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "作品资料保存失败。"); }
  }

  return (
    <AdminShell active="/admin/showcase">
      <AdminPageLayout eyebrow="WORKS & SHOWCASE" title="作品审核与展示墙" description="审核学生作品，精选通过的作品可进入创作岛首页展示。"><AdminSection title="首页展示规则" description="规则会保存为机构级配置，并供学生创作大厅读取。" toolbar={<button className="admin-primary-button" type="button" onClick={() => void saveRules()}>保存展示规则</button>}><div className="showcase-admin__grid"><label>每行作品数<select value={settings.showcaseColumns} onChange={(event) => setSettings({ ...settings, showcaseColumns: Number(event.target.value) })}><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option></select></label><label>展示行数<select value={settings.showcaseRows} onChange={(event) => setSettings({ ...settings, showcaseRows: Number(event.target.value) })}><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></label><label>排序方式<select value={settings.showcaseSort} onChange={(event) => setSettings({ ...settings, showcaseSort: event.target.value as OrganizationSettings["showcaseSort"] })}><option value="featured">精选优先</option><option value="newest">最新发布</option><option value="popular">最受欢迎</option></select></label><label>展示类型<select value={settings.showcaseKind} onChange={(event) => setSettings({ ...settings, showcaseKind: event.target.value as OrganizationSettings["showcaseKind"] })}><option value="all">全部</option><option value="webpage">网页</option><option value="image">图片</option><option value="music">音乐</option><option value="video">视频</option></select></label></div></AdminSection><AdminSection title="待审核作品" description="审核通过后可标记为首页精选作品；也可以编辑封面、步骤和适用年级。" toolbar={<div className="admin-heading-actions">{selected.length > 0 && <><button className="admin-primary-button" type="button" onClick={() => void batchReview("approved", true)}>通过并精选({selected.length})</button><button className="admin-button--quiet" type="button" onClick={() => void batchReview("rejected", false)}>批量退回({selected.length})</button></>}</div>}>{status && <div className="admin-feedback" role="status">{status}</div>}<div className="admin-log-table"><div className="admin-log-head"><span>作品</span><span>类型</span><span>学生</span><span>状态</span><span>操作</span></div>{works.map((work) => <div key={work.assetId}><span><input type="checkbox" checked={selected.includes(work.assetId)} onChange={() => toggleSelected(work.assetId)} /> {work.title}</span><span>{work.kind}</span><span>{work.ownerUserId}</span><span>{work.reviewState}</span><span><button type="button" onClick={() => setEditing(work)}>编辑资料</button><button type="button" onClick={() => void review(work.assetId, "approved", true)}>通过并精选</button><button type="button" onClick={() => void review(work.assetId, "rejected", false)}>退回</button></span></div>)}</div></AdminSection>{editing && <AdminSection title="编辑作品资料" description="这些资料会显示在作品墙与作品详情，支持后期反复修改。" toolbar={<button className="admin-button--quiet" type="button" onClick={() => setEditing(null)}>取消</button>}><form className="showcase-admin__grid" onSubmit={(event) => void saveMetadata(event)}><label>作品名称<input name="title" required defaultValue={editing.title} /></label><label>作品预览地址<input name="previewUrl" defaultValue={editing.previewUrl} placeholder="/samples/xxx.mp4 或 COS 地址" /></label><label>封面图片地址<input name="coverUrl" defaultValue={editing.coverUrl} placeholder="封面图地址（图片作品可留空）" /></label><label>上传封面图<input name="coverFile" type="file" accept="image/png,image/jpeg,image/webp,image/gif" /></label><label>上传预览文件<input name="previewFile" type="file" accept={editing.kind === "video" ? "video/mp4,video/webm" : editing.kind === "music" ? "audio/mpeg,audio/wav,audio/x-m4a" : "image/png,image/jpeg,image/webp,image/gif"} /></label><label>展示范围<select name="visibility" defaultValue={editing.visibility}><option value="organization">机构作品墙</option><option value="private">仅作者和老师</option></select></label><label>起始年级<select name="gradeMin" defaultValue={editing.gradeMin}>{[3, 4, 5, 6].map((grade) => <option key={grade} value={grade}>{grade} 年级</option>)}</select></label><label>结束年级<select name="gradeMax" defaultValue={editing.gradeMax}>{[3, 4, 5, 6].map((grade) => <option key={grade} value={grade}>{grade} 年级</option>)}</select></label><label className="admin-checkbox-row"><input name="isExample" type="checkbox" defaultChecked={editing.isExample} /> 这是教师示例作品</label><label className="admin-wide-field">创作步骤（每行一步）<textarea name="steps" rows={5} defaultValue={editing.processSteps.join("\n")} placeholder="选择主题\n告诉 AI 画面里的主角和细节\n预览后再修改一次" /></label><div><button className="admin-primary-button" type="submit">保存作品资料</button></div></form></AdminSection>}</AdminPageLayout>
    </AdminShell>
  );
}
