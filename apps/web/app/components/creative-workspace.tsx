"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, Copy, Download, ImagePlus, Music2, Palette, Send, Sparkles, Star, Video } from "lucide-react";
import { createMediaJob, createWork, currentSession, generateText, getMediaJob, getWork, polishPrompt, resolveWorkMediaUrl, uploadReferenceImage, type CreativeWork } from "../../src/api-client";

export type CreativeKind = "chat" | "image" | "music" | "video";

type WorkspaceConfig = { name: string; icon: typeof Bot; placeholder: string; presets: string[]; steps: string[] };
type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onresult: ((event: { results: { length: number; [index: number]: { 0: { transcript: string } } } }) => void) | null;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

const WORKSPACES: Record<CreativeKind, WorkspaceConfig> = {
  chat: { name: "AI 对话", icon: Bot, placeholder: "告诉 AI 你想完成什么任务，例如：帮我想一个保护海洋的故事主角。", presets: ["故事伙伴", "学习助手", "网页老师"], steps: ["说出你的目标", "和 AI 一起完善", "把成果放进作品夹"] },
  image: { name: "AI 绘画", icon: Palette, placeholder: "例：一只戴着护目镜的小海龟，正在珊瑚城里修理潜水艇，Q版卡通风格。", presets: ["Q版卡通", "儿童绘画", "水彩画", "像素世界", "中国风", "油画"], steps: ["想好主角", "选择画面风格", "生成并收藏作品"] },
  music: { name: "AI 音乐", icon: Music2, placeholder: "例：操场上的接力赛，快乐、有力量，适合大家一起唱。", presets: ["流行", "国风", "民谣", "朋克", "爵士", "电子"], steps: ["写下主题或歌词", "选择音乐风格", "收听并保存歌曲"] },
  video: { name: "AI 视频", icon: Video, placeholder: "例：小机器人从书包里飞出，在星空中画出一条会发光的数学公式。", presets: ["图生视频", "文生视频"], steps: ["选择创作方式", "添加画面描述", "等待作品生成"] },
};

const rails: Array<{ href: string; label: string; icon: typeof Bot; kind?: CreativeKind }> = [
  { href: "/workspace/chat", label: "大语言模型", icon: Bot, kind: "chat" }, { href: "/workspace/image", label: "AI绘画", icon: Palette, kind: "image" }, { href: "/workspace/html", label: "网页创作", icon: Sparkles }, { href: "/workspace/music", label: "AI音乐", icon: Music2, kind: "music" }, { href: "/workspace/video", label: "AI视频", icon: Video, kind: "video" }, { href: "/agents", label: "智能体中心", icon: Sparkles },
];

function UploadBox({ label, compact = false, onSelect, selected }: { label: string; compact?: boolean; onSelect: (file: File) => void; selected?: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return <button type="button" className={`studio-upload ${compact ? "studio-upload--compact" : ""}`} onClick={() => inputRef.current?.click()}><input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onSelect(file); }} /><ImagePlus size={compact ? 24 : 30} /><b>{selected || label}</b><small>JPG、PNG、WEBP，5MB 以内</small></button>;
}

export function CreativeWorkspace({ kind }: { kind: CreativeKind }) {
  const config = WORKSPACES[kind];
  const Icon = config.icon;
  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [selectedPreset, setSelectedPreset] = useState(config.presets[0]);
  const [imageRatio, setImageRatio] = useState("16:9");
  const [imageHint, setImageHint] = useState("");
  const [videoMode, setVideoMode] = useState("图生视频");
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("准备好啦，写下你的想法吧！");
  const [result, setResult] = useState("");
  const [mediaWork, setMediaWork] = useState<CreativeWork | null>(null);
  const [referenceImageUrl, setReferenceImageUrl] = useState("");
  const [referenceName, setReferenceName] = useState("");
  const [flowOpen, setFlowOpen] = useState(false);
  const [polishingField, setPolishingField] = useState<string | null>(null);

  useEffect(() => {
    const starterPrompt = new URLSearchParams(window.location.search).get("prompt")?.trim() ?? "";
    if (!starterPrompt) return;
    setPrompt(starterPrompt);
    setStatus("老师已经帮你准备好创作提示，看看后可以直接生成或修改。");
  }, []);
  const formReady = prompt.trim().length > 0 && (kind !== "music" || title.trim().length > 0) && (kind !== "video" || videoMode !== "图生视频" || Boolean(referenceImageUrl));
  const outputDescription = useMemo(() => {
    if (kind === "music") return `${title} · ${selectedPreset}`;
    if (kind === "video") return videoMode;
    if (kind === "image") return [selectedPreset, imageRatio, imageHint.trim()].filter(Boolean).join(" · ");
    return selectedPreset;
  }, [imageHint, imageRatio, kind, selectedPreset, title, videoMode]);

  async function watchMediaJob(accessToken: string, jobId: string) {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 4000));
      try {
        const job = await getMediaJob(accessToken, jobId);
        if (job.state === "succeeded") {
          const work = job.assetId ? await getWork(accessToken, job.assetId) : null;
          setMediaWork(work);
          setStatus("创作完成，已自动保存到作品夹，等待老师审核");
          setResult("作品已经完成啦！它已自动进入“我的作品夹”，老师审核通过后还可能出现在作品展示区。\n\n你可以继续开始下一次创作。 ");
          return;
        }
        if (job.state === "failed") {
          setStatus(job.error || "这次创作没有完成，可以修改描述后重试");
          return;
        }
      } catch {
        return;
      }
    }
  }

  async function submit() {
    const session = currentSession();
    if (!session || !formReady) { setStatus(session ? "请先补全这次创作的小任务" : "请先登录你的平台账号"); return; }
    setStatus("AI 正在认真创作中…");
    try {
      if (kind === "chat") {
        const response = await generateText(session.accessToken, prompt);
        await createWork(session.accessToken, {
          projectId: `text-${session.userId}`,
          kind: "text",
          title: `AI 对话：${prompt.slice(0, 18)}`,
          prompt,
        });
        setResult(response.content);
        setStatus("回答已自动保存到作品夹，等待老师审核");
      } else {
        const response = await createMediaJob(session.accessToken, kind, `${outputDescription}：${prompt}`, referenceImageUrl || undefined);
        setResult(`已进入创作队列。任务状态：${response.state}。生成完成后会自动保存到“我的作品夹”，再进入老师审核流程。`);
        setStatus("创作任务已提交，正在等待生成");
        void watchMediaJob(session.accessToken, response.jobId);
      }
    } catch (error) { setStatus(error instanceof Error ? error.message : "暂时无法提交创作任务"); }
  }

  async function selectReferenceImage(file: File) {
    const session = currentSession();
    if (!session) return setStatus("请先登录你的平台账号");
    setStatus("正在安全上传参考图…");
    try {
      setReferenceImageUrl(await uploadReferenceImage(session.accessToken, file));
      setReferenceName(file.name);
      setStatus("参考图已准备好，可以开始创作啦！");
    } catch (error) { setStatus(error instanceof Error ? error.message : "参考图上传失败"); }
  }

  async function polish(value: string, apply: (next: string) => void, field: string) {
    const session = currentSession();
    if (!session) return setStatus("请先登录你的平台账号");
    if (!value.trim()) return setStatus("先写下一点想法，再让 AI 帮你润色吧。");
    setPolishingField(field);
    setStatus("AI 正在把你的想法整理得更清楚…");
    try {
      const capability = kind === "chat" ? "text" : kind;
      const result = await polishPrompt(session.accessToken, capability, value.trim());
      apply(result.content);
      setStatus("润色完成！你可以继续修改，也可以直接生成。 ");
    } catch (error) { setStatus(error instanceof Error ? error.message : "润色暂时不可用，请稍后再试。"); }
    finally { setPolishingField(null); }
  }

  function startVoiceInput() {
    const speechWindow = window as Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setStatus("当前浏览器不支持语音输入，请使用 Chrome 或 Edge 输入文字。");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onstart = () => { setListening(true); setStatus("正在听你说话…说完后会自动填入创意描述。"); };
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) transcript += event.results[index][0].transcript;
      if (transcript.trim()) setPrompt((current) => `${current}${current.trim() ? " " : ""}${transcript.trim()}`);
    };
    recognition.onerror = (event) => setStatus(event.error === "not-allowed" ? "需要允许麦克风权限才能使用语音输入。" : "没有听清楚，请再试一次或直接输入文字。");
    recognition.onend = () => setListening(false);
    try { recognition.start(); } catch { setListening(false); setStatus("语音输入暂时无法启动，请稍后重试。"); }
  }

  function reset() { setPrompt(""); setTitle(""); setImageHint(""); setResult(""); setMediaWork(null); setReferenceImageUrl(""); setReferenceName(""); setStatus("已清空，可以开始新的创作"); }

  return <main className="studio">
    <header className="studio-head"><a href="/" className="studio-logo"><Sparkles size={18} /> 星芽AI</a><b>AI工坊</b><a href="/" className="studio-back">← 返回创作岛</a><span /><a href="/projects" className="studio-collection"><Star size={18} /> 我的作品夹</a><i aria-label="学生头像">😊</i></header>
    <aside className="studio-nav" aria-label="创作类别">{rails.map((rail) => { const RailIcon = rail.icon; return <a key={rail.href} href={rail.href} className={rail.kind === kind ? "on" : ""}><RailIcon size={25} strokeWidth={2.1} /><small>{rail.label}</small></a>; })}</aside>
    <section className="studio-form" aria-label={`${config.name}任务设置`}>
      {kind === "chat" && <AgentPicker selected={selectedPreset} presets={config.presets} onSelect={setSelectedPreset} />}
      {kind === "music" && <label className="studio-field">歌曲名称<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={20} placeholder="给这首歌起个名字" /><span className="studio-field__bottom"><button type="button" disabled={polishingField === "title"} onClick={() => void polish(title, setTitle, "title")}>{polishingField === "title" ? "润色中…" : "✨ 帮我润色"}</button><small>{title.length}/20</small></span></label>}
      {kind === "video" && <><div className="studio-segmented">{config.presets.map((preset) => <button key={preset} className={videoMode === preset ? "selected" : ""} onClick={() => setVideoMode(preset)}>{preset}</button>)}</div>{videoMode === "图生视频" && <UploadBox label="上传参考图（必选）" selected={referenceName} onSelect={(file) => void selectReferenceImage(file)} />}</>}
      {kind === "image" && <ImageControls selected={selectedPreset} presets={config.presets} onSelect={setSelectedPreset} ratio={imageRatio} onRatioChange={setImageRatio} hint={imageHint} onHintChange={setImageHint} onPolish={() => void polish(imageHint, setImageHint, "image-hint")} polishing={polishingField === "image-hint"} />}
      <label className="studio-field studio-field--prompt">{kind === "music" ? "创意歌词 / 音乐主题" : "创意描述"}<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={500} placeholder={config.placeholder} /><span className="studio-field__bottom"><button type="button" disabled={listening} onClick={startVoiceInput}>{listening ? "🎙 正在聆听…" : "🎙 语音输入"}</button><button type="button" disabled={polishingField === "prompt"} onClick={() => void polish(prompt, setPrompt, "prompt")}>{polishingField === "prompt" ? "润色中…" : "✨ 帮我润色"}</button><small>{prompt.length}/500</small></span></label>
      {kind !== "image" && kind !== "video" && <PresetChips label={kind === "music" ? "音乐风格" : "选择一位 AI 伙伴"} presets={config.presets} selected={selectedPreset} onSelect={setSelectedPreset} />}
      {kind === "image" && <UploadBox label="上传参考图（可选）" selected={referenceName} compact onSelect={(file) => void selectReferenceImage(file)} />}
      <div className="studio-actions"><button type="button" onClick={reset}>重置</button><button type="button" disabled={!formReady} onClick={() => void submit()}><Send size={17} /> 立即生成</button></div>
    </section>
    <section className="studio-stage" aria-live="polite"><div className="studio-stage__bar"><span><Icon size={21} /> {config.name} · 创作记录</span><div><small>{status}</small><button type="button" className="studio-flow-button" onClick={() => setFlowOpen((open) => !open)}>{flowOpen ? "收起流程" : "查看教学流程"}</button></div></div>{flowOpen ? <div className="studio-flow-panel"><h2>本节课怎么完成？</h2><p>跟着下面的步骤做，不需要打开代码，也不用一次想完全部内容。</p>{config.steps.map((step, index) => <div className="studio-flow-step" key={step}><b>{index + 1}</b><span>{step}</span></div>)}<div className="studio-flow-tip">小提示：遇到不会的地方，可以直接把问题告诉 AI 伙伴。</div></div> : result ? <article className="studio-result"><div className="studio-result__tag"><Icon size={19} /> 本次作品 · {outputDescription}</div><h2>你的创作结果</h2><p>{result}</p>{mediaWork && <MediaPreview work={mediaWork} />}<footer><button type="button" onClick={() => navigator.clipboard?.writeText(prompt)}><Copy size={17} /> 复制提示词</button>{mediaWork?.previewUrl && <a href={mediaWork.previewUrl} download target="_blank" rel="noreferrer"><Download size={17} /> 下载作品</a>}<a href="/projects"><Star size={17} /> 查看作品夹</a></footer></article> : <div className="studio-empty"><span className="studio-empty__icon"><Icon size={44} /></span><h2>还没有创作记录</h2><p>左侧完成任务，这里会展示你的作品和创作过程。</p><ol>{config.steps.map((step, index) => <li key={step}><b>{index + 1}</b>{step}</li>)}</ol></div>}</section>
  </main>;
}

function AgentPicker({ selected, presets, onSelect }: { selected: string; presets: string[]; onSelect: (preset: string) => void }) { return <div className="studio-agent-picker"><span>和谁一起完成任务？</span><div>{presets.map((preset) => <button type="button" key={preset} className={selected === preset ? "selected" : ""} onClick={() => onSelect(preset)}><Bot size={16} /> {preset}</button>)}</div></div>; }
function ImageControls({ selected, presets, onSelect, ratio, onRatioChange, hint, onHintChange, onPolish, polishing }: { selected: string; presets: string[]; onSelect: (preset: string) => void; ratio: string; onRatioChange: (ratio: string) => void; hint: string; onHintChange: (hint: string) => void; onPolish: () => void; polishing: boolean }) { return <><label className="studio-field">画面小提示<input value={hint} onChange={(event) => onHintChange(event.target.value)} maxLength={120} placeholder="例如：主角在操场奔跑，远处有彩虹" /><span className="studio-field__bottom"><button type="button" disabled={polishing} onClick={onPolish}>{polishing ? "润色中…" : "✨ 帮我润色"}</button><small>{hint.length}/120</small></span></label><PresetChips label="艺术风格" presets={presets} selected={selected} onSelect={onSelect} visual /><PresetChips label="图片比例" presets={["16:9", "9:16", "1:1"]} selected={ratio} onSelect={onRatioChange} /></>; }
function PresetChips({ label, presets, selected, onSelect, visual = false }: { label: string; presets: string[]; selected: string; onSelect: (preset: string) => void; visual?: boolean }) { return <div className={visual ? "studio-presets studio-presets--visual" : "studio-presets"}><h3>{label}</h3><div>{presets.map((preset, index) => <button type="button" key={preset} className={selected === preset ? "selected" : ""} onClick={() => onSelect(preset)}>{visual && <i className={`studio-style-thumb studio-style-thumb--${index}`} />} {preset}</button>)}</div></div>; }

function MediaPreview({ work }: { work: CreativeWork }) {
  if (!work.previewUrl) return null;
  if (work.kind === "image") return <img className="studio-media-preview" src={resolveWorkMediaUrl(work.previewUrl)} alt={work.title} />;
  if (work.kind === "video") return <video className="studio-media-preview" controls src={resolveWorkMediaUrl(work.previewUrl)}>你的浏览器暂不支持播放视频。</video>;
  if (work.kind === "music" || work.kind === "text") return <audio className="studio-audio-preview" controls src={resolveWorkMediaUrl(work.previewUrl)}>你的浏览器暂不支持播放音频。</audio>;
  return null;
}
