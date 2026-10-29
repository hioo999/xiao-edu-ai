"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, Copy, Download, ImagePlus, Music2, Palette, Send, Sparkles, Star, Video } from "lucide-react";
import { createMediaJob, createWork, currentSession, generateText, getMediaJob, getWork, polishPrompt, uploadReferenceImage, type CreativeWork } from "../../src/api-client";
import { buildWordDocument, safeDownloadName } from "../../src/creative-text-export";
import { buildMusicLyricsPrompt, requireGeneratedLyrics } from "../../src/music-creation";
import { FormattedCreativeText } from "./formatted-creative-text";
import { CreationHeader } from "./creation-header";
import { useWorkMediaUrl } from "./use-work-media-url";

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
  image: { name: "AI 绘画", icon: Palette, placeholder: "例：一只戴着护目镜的小海龟，正在珊瑚城里修理潜水艇，Q版卡通风格。", presets: ["Q版卡通", "儿童绘本", "水彩童话", "像素世界", "中国风", "黏土玩具", "赛博霓虹", "剪纸拼贴", "3D盲盒", "魔法油画"], steps: ["想好主角", "选择画面风格", "生成并收藏作品"] },
  music: { name: "AI 音乐", icon: Music2, placeholder: "例：操场上的接力赛，快乐、有力量，适合大家一起唱。", presets: ["流行", "国风", "民谣", "朋克", "爵士", "电子"], steps: ["写下主题或歌词", "选择音乐风格", "收听并保存歌曲"] },
  video: { name: "AI 视频", icon: Video, placeholder: "例：小机器人从书包里飞出，在星空中画出一条会发光的数学公式。", presets: ["图生视频", "文生视频"], steps: ["选择创作方式", "添加画面描述", "等待作品生成"] },
};

const STYLE_EXAMPLES: Record<string, { icon: string; hint: string }> = {
  "Q版卡通": { icon: "🐰", hint: "圆圆脸、大眼睛" },
  "儿童绘本": { icon: "📖", hint: "温柔故事感" },
  "水彩童话": { icon: "🌈", hint: "淡淡晕染" },
  "像素世界": { icon: "🟦", hint: "方块小游戏" },
  "中国风": { icon: "🏮", hint: "云纹和水墨" },
  "黏土玩具": { icon: "🧸", hint: "软软立体感" },
  "赛博霓虹": { icon: "✨", hint: "发光未来城" },
  "剪纸拼贴": { icon: "✂️", hint: "彩纸层次" },
  "3D盲盒": { icon: "🎁", hint: "可爱模型感" },
  "魔法油画": { icon: "🪄", hint: "厚涂光影" },
};

function activeJobKey(organizationId: string, userId: string, kind: CreativeKind): string {
  return `ai-workbench-active-job:${organizationId}:${userId}:${kind}`;
}

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
  const [videoRatio, setVideoRatio] = useState("16:9");
  const [imageHint, setImageHint] = useState("");
  const [videoMode, setVideoMode] = useState("图生视频");
  const [videoDuration, setVideoDuration] = useState("5 秒");
  const [videoMotion, setVideoMotion] = useState("镜头推进");
  const [musicMood, setMusicMood] = useState("快乐");
  const [musicVoice, setMusicVoice] = useState("童声合唱");
  const [musicSpeed, setMusicSpeed] = useState("中速");
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("准备好啦，写下你的想法吧！");
  const [result, setResult] = useState("");
  const [mediaWork, setMediaWork] = useState<CreativeWork | null>(null);
  const mediaSource = useWorkMediaUrl(mediaWork?.previewUrl ?? "");
  const [referenceImageUrl, setReferenceImageUrl] = useState("");
  const [referenceName, setReferenceName] = useState("");
  const [flowOpen, setFlowOpen] = useState(false);
  const [polishingField, setPolishingField] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const pollRunRef = useRef(0);
  const [musicInputMode, setMusicInputMode] = useState<"theme" | "lyrics">("theme");
  const [signedIn, setSignedIn] = useState<boolean | null>(null);

  useEffect(() => {
    setSignedIn(Boolean(currentSession()));
    const starterPrompt = new URLSearchParams(window.location.search).get("prompt")?.trim() ?? "";
    if (!starterPrompt) return;
    setPrompt(starterPrompt);
    setStatus("老师已经帮你准备好创作提示，看看后可以直接生成或修改。");
  }, []);
  useEffect(() => {
    const session = currentSession();
    if (kind !== "chat" && session) {
      const storageKey = activeJobKey(session.organizationId, session.userId, kind);
      const jobId = window.sessionStorage.getItem(storageKey);
      if (jobId) {
        setPending(true);
        setStatus("正在恢复上次的创作进度…");
        void watchMediaJob(session.accessToken, jobId, storageKey, ++pollRunRef.current);
      }
    }
    return () => { pollRunRef.current += 1; };
  }, [kind]);
  const formReady = prompt.trim().length > 0 && (kind !== "music" || title.trim().length > 0) && (kind !== "video" || videoMode !== "图生视频" || Boolean(referenceImageUrl));
  const outputDescription = useMemo(() => {
    if (kind === "music") return `${title} · ${selectedPreset}`;
    if (kind === "video") return `${videoMode} · ${videoRatio}`;
    if (kind === "image") return [selectedPreset, imageRatio, imageHint.trim()].filter(Boolean).join(" · ");
    return selectedPreset;
  }, [imageHint, imageRatio, kind, selectedPreset, title, videoMode, videoRatio]);

  async function watchMediaJob(accessToken: string, jobId: string, storageKey: string, pollRun: number) {
    let consecutiveFailures = 0;
    for (let attempt = 0; attempt < 90; attempt += 1) {
      if (attempt > 0) await new Promise((resolve) => window.setTimeout(resolve, 4000));
      if (pollRun !== pollRunRef.current) return;
      try {
        const job = await getMediaJob(accessToken, jobId);
        if (pollRun !== pollRunRef.current) return;
        consecutiveFailures = 0;
        if (job.state === "succeeded") {
          const work = job.assetId ? await getWork(accessToken, job.assetId) : null;
          if (pollRun !== pollRunRef.current) return;
          if (!work?.previewUrl) throw new Error("作品已生成，但暂时无法读取媒体文件，请稍后到作品夹查看。");
          if (window.sessionStorage.getItem(storageKey) === jobId) window.sessionStorage.removeItem(storageKey);
          setMediaWork(work);
          setStatus("创作完成");
          setResult("作品已经完成啦！");
          setPending(false);
          return;
        }
        if (job.state === "failed") {
          if (window.sessionStorage.getItem(storageKey) === jobId) window.sessionStorage.removeItem(storageKey);
          setStatus(job.error || "这次创作没有完成，可以修改描述后重试");
          setPending(false);
          return;
        }
      } catch {
        if (pollRun !== pollRunRef.current) return;
        consecutiveFailures += 1;
        if (consecutiveFailures >= 3) {
          setStatus("暂时无法确认生成进度，请到作品夹查看结果，或稍后重新打开页面。");
          setPending(false);
          return;
        }
        setStatus("网络不稳定，正在重新查询创作进度…");
      }
    }
    setStatus("生成时间较长，请稍后到作品夹查看，不要重复提交。");
    setPending(false);
  }

  async function submit() {
    const session = currentSession();
    if (!session || !formReady || pending) { setStatus(session ? "请先补全这次创作的小任务，或等待当前任务完成" : "请先登录你的平台账号"); return; }
    setPending(true);
    setMediaWork(null);
    setResult("");
    setStatus("AI 正在认真创作中…");
    try {
      if (kind === "chat") {
        const response = await generateText(session.accessToken, prompt);
        await createWork(session.accessToken, {
          projectId: `text-${session.userId}`,
          kind: "text",
          title: `AI 对话：${prompt.slice(0, 18)}`,
          prompt,
          content: response.content,
        });
        setResult(response.content);
        setStatus("创作完成");
      } else {
        let lyrics = "";
        if (kind === "music") {
          if (musicInputMode === "theme") {
            setStatus("正在根据主题创作歌词…");
            const lyricResponse = await generateText(session.accessToken, buildMusicLyricsPrompt(title, prompt));
            lyrics = requireGeneratedLyrics(lyricResponse.content);
          } else {
            lyrics = prompt.trim();
          }
        }
        const mediaPrompt = kind === "music" ? `${title}，${selectedPreset}风格，${musicMood}情绪，${musicVoice}，${musicSpeed}。请用以下歌词谱曲并演唱：\n${lyrics}` : kind === "video" ? `${outputDescription}，时长${videoDuration}，${videoMotion}：${prompt}` : `${outputDescription}：${prompt}`;
        const mediaReference = kind === "video" && videoMode !== "图生视频" ? undefined : referenceImageUrl || undefined;
        const response = await createMediaJob(session.accessToken, kind, mediaPrompt, mediaReference, { title, lyrics: kind === "music" ? lyrics : undefined, aspectRatio: kind === "image" ? imageRatio : kind === "video" ? videoRatio : undefined });
        const storageKey = activeJobKey(session.organizationId, session.userId, kind);
        window.sessionStorage.setItem(storageKey, response.jobId);
        setResult("");
        setStatus("正在生成…");
        void watchMediaJob(session.accessToken, response.jobId, storageKey, ++pollRunRef.current);
      }
    } catch (error) { setPending(false); setStatus(error instanceof Error ? error.message : "暂时无法提交创作任务"); }
    if (kind === "chat") setPending(false);
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

  function reset() { if (pending) return; setPrompt(""); setTitle(""); setImageHint(""); setResult(""); setMediaWork(null); setReferenceImageUrl(""); setReferenceName(""); setVideoDuration("5 秒"); setVideoMotion("镜头推进"); setMusicMood("快乐"); setMusicVoice("童声合唱"); setMusicSpeed("中速"); setStatus("已清空，可以开始新的创作"); }

  function scrollWorkspace(direction: "up" | "down") {
    window.scrollBy({ top: direction === "up" ? -Math.max(window.innerHeight * 0.78, 420) : Math.max(window.innerHeight * 0.78, 420), behavior: "smooth" });
  }

  async function copyResult() {
    try {
      await navigator.clipboard?.writeText(result);
      setStatus("正文已复制，可以粘贴到作业或教学文档里啦！");
    } catch {
      setStatus("复制失败，请检查浏览器的剪贴板权限。");
    }
  }

  function downloadWord() {
    const blob = new Blob([`\ufeff${buildWordDocument("AI创作结果", result)}`], { type: "application/msword;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeDownloadName("AI创作结果")}.doc`;
    link.click();
    URL.revokeObjectURL(url);
    setStatus("Word 文档已下载，可以用 Word 或 WPS 打开。");
  }

  const promptField = <label className={`studio-field studio-field--prompt ${kind === "image" ? "studio-field--prompt-large" : ""}`}>{kind === "music" ? (musicInputMode === "theme" ? "歌曲主题" : "完整歌词") : "创意描述"}<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={500} placeholder={kind === "music" && musicInputMode === "lyrics" ? "写下主歌和副歌，AI 会帮你谱曲演唱。" : config.placeholder} /><span className="studio-field__bottom"><button type="button" disabled={listening} onClick={startVoiceInput}>{listening ? "🎙 正在聆听…" : "🎙 语音输入"}</button><button type="button" disabled={polishingField === "prompt"} onClick={() => void polish(prompt, setPrompt, "prompt")}>{polishingField === "prompt" ? "润色中…" : "✨ 帮我润色"}</button><small>{prompt.length}/500</small></span></label>;

  if (signedIn === false) return <main className="catalog-shell"><header className="catalog-header"><p className="student-home__eyebrow">CREATION ISLAND</p><h1>登录后开始创作</h1><p>登录后才能使用 AI 创作工具，生成的作品也会自动保存到你的作品夹。</p><a className="teacher-primary-link" href={`/login?next=${encodeURIComponent(`/workspace/${kind}`)}`}>登录后继续</a><a className="teacher-secondary-link" href="/">返回创作大厅</a></header></main>;
  if (signedIn === null) return <main className="catalog-shell"><p className="course-upload-status">正在检查登录状态…</p></main>;
  return <main className="studio creation-surface unified-studio">
    <CreationHeader title={config.name + "创作小屋"} description={config.steps.join(" → ")} active={"/workspace/" + kind} />
    <section className="studio-form" aria-label={`${config.name}任务设置`}>
      {kind === "chat" && <AgentPicker selected={selectedPreset} presets={config.presets} onSelect={setSelectedPreset} />}
      {kind === "music" && <label className="studio-field">歌曲名称<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={20} placeholder="给这首歌起个名字" /><span className="studio-field__bottom"><button type="button" disabled={polishingField === "title"} onClick={() => void polish(title, setTitle, "title")}>{polishingField === "title" ? "润色中…" : "✨ 帮我润色"}</button><small>{title.length}/20</small></span></label>}
      {kind === "music" && <div className="studio-segmented" aria-label="歌词来源"><button type="button" className={musicInputMode === "theme" ? "selected" : ""} onClick={() => { setMusicInputMode("theme"); setPrompt(""); }}>根据主题生成歌词</button><button type="button" className={musicInputMode === "lyrics" ? "selected" : ""} onClick={() => { setMusicInputMode("lyrics"); setPrompt(""); }}>使用自己写的歌词</button></div>}
      {kind === "video" && <><div className="studio-segmented">{config.presets.map((preset) => <button type="button" key={preset} className={videoMode === preset ? "selected" : ""} onClick={() => setVideoMode(preset)}>{preset}</button>)}</div>{videoMode === "图生视频" && <UploadBox label="上传参考图（必选）" selected={referenceName} onSelect={(file) => void selectReferenceImage(file)} />}<PresetChips label="视频画幅" presets={["16:9", "9:16", "1:1", "4:3", "3:4"]} selected={videoRatio} onSelect={setVideoRatio} /><PresetChips label="视频时长" presets={["5 秒", "10 秒"]} selected={videoDuration} onSelect={setVideoDuration} /><PresetChips label="镜头动作" presets={["镜头推进", "镜头拉远", "左右移动", "环境动态"]} selected={videoMotion} onSelect={setVideoMotion} /></>}
      {kind === "image" && promptField}
      {kind === "image" && <ImageControls selected={selectedPreset} presets={config.presets} onSelect={setSelectedPreset} ratio={imageRatio} onRatioChange={setImageRatio} hint={imageHint} onHintChange={setImageHint} onPolish={() => void polish(imageHint, setImageHint, "image-hint")} polishing={polishingField === "image-hint"} />}
      {kind !== "image" && promptField}
      {kind !== "image" && kind !== "video" && <PresetChips label={kind === "music" ? "音乐风格" : "选择一位 AI 伙伴"} presets={config.presets} selected={selectedPreset} onSelect={setSelectedPreset} />}
      {kind === "music" && <><PresetChips label="歌曲情绪" presets={["快乐", "温柔", "勇敢", "神秘", "热血"]} selected={musicMood} onSelect={setMusicMood} /><PresetChips label="演唱方式" presets={["童声合唱", "女声", "男声", "轻声演唱"]} selected={musicVoice} onSelect={setMusicVoice} /><PresetChips label="演唱速度" presets={["慢速", "中速", "快速"]} selected={musicSpeed} onSelect={setMusicSpeed} /></>}
      {kind === "image" && <UploadBox label="上传参考图（可选）" selected={referenceName} compact onSelect={(file) => void selectReferenceImage(file)} />}
      <div className="studio-actions"><button type="button" disabled={pending} onClick={reset}>重置</button><button type="button" disabled={!formReady || pending} onClick={() => void submit()}><Send size={17} /> {pending ? "创作中…" : "立即生成"}</button></div>
    </section>
    <section className="studio-stage" aria-live="polite"><div className="studio-stage__bar"><span><Icon size={21} /> {config.name} · 创作记录</span><div><small>{status}</small><button type="button" className="studio-flow-button" onClick={() => setFlowOpen((open) => !open)}>{flowOpen ? "收起流程" : "查看教学流程"}</button></div></div>{flowOpen ? <div className="studio-flow-panel"><h2>本节课怎么完成？</h2><p>跟着下面的步骤做，不需要打开代码，也不用一次想完全部内容。</p>{config.steps.map((step, index) => <div className="studio-flow-step" key={step}><b>{index + 1}</b><span>{step}</span></div>)}<div className="studio-flow-tip">小提示：遇到不会的地方，可以直接把问题告诉 AI 伙伴。</div></div> : result ? <article className="studio-result"><div className="studio-result__tag"><Icon size={19} /> 本次作品 · {outputDescription}</div><h2>你的创作结果</h2><FormattedCreativeText text={result} />{mediaWork && <MediaPreview work={mediaWork} source={mediaSource} />}<footer>{kind === "image" && <button type="button" disabled={pending} onClick={() => void submit()}>相似重生成</button>}<button type="button" onClick={() => void copyResult()}><Copy size={17} /> 复制正文</button>{kind === "chat" && <button type="button" onClick={downloadWord}><Download size={17} /> 下载 Word</button>}{mediaWork?.lyrics && <button type="button" onClick={() => void navigator.clipboard?.writeText(mediaWork.lyrics)}><Copy size={17} /> 复制歌词</button>}<button type="button" onClick={() => navigator.clipboard?.writeText(prompt)}><Copy size={17} /> 复制提示词</button>{mediaWork?.previewUrl && <a href={mediaSource || undefined} aria-disabled={!mediaSource} download target="_blank" rel="noreferrer"><Download size={17} /> 下载作品</a>}<a href="/projects"><Star size={17} /> 查看作品夹</a></footer></article> : <div className="studio-empty"><span className="studio-empty__icon"><Icon size={44} /></span><h2>还没有创作记录</h2><p>左侧完成任务，这里会展示你的作品和创作过程。</p><ol>{config.steps.map((step, index) => <li key={step}><b>{index + 1}</b>{step}</li>)}</ol></div>}</section>
    <nav className="studio-scroll-controls" aria-label="工作台页面导航"><button type="button" aria-label="向上查看输入区" title="向上查看输入区" onClick={() => scrollWorkspace("up")}>↑</button><button type="button" aria-label="向下查看生成结果" title="向下查看生成结果" onClick={() => scrollWorkspace("down")}>↓</button></nav>
  </main>;
}

function AgentPicker({ selected, presets, onSelect }: { selected: string; presets: string[]; onSelect: (preset: string) => void }) { return <div className="studio-agent-picker"><span>和谁一起完成任务？</span><div>{presets.map((preset) => <button type="button" key={preset} className={selected === preset ? "selected" : ""} onClick={() => onSelect(preset)}><Bot size={16} /> {preset}</button>)}</div></div>; }
function ImageControls({ selected, presets, onSelect, ratio, onRatioChange, hint, onHintChange, onPolish, polishing }: { selected: string; presets: string[]; onSelect: (preset: string) => void; ratio: string; onRatioChange: (ratio: string) => void; hint: string; onHintChange: (hint: string) => void; onPolish: () => void; polishing: boolean }) { return <><PresetChips label="艺术风格" presets={presets} selected={selected} onSelect={onSelect} visual /><PresetChips label="图片比例" presets={["16:9", "9:16", "3:4", "4:3", "1:1"]} selected={ratio} onSelect={onRatioChange} /><label className="studio-field">画面小提示<input value={hint} onChange={(event) => onHintChange(event.target.value)} maxLength={120} placeholder="例如：主角在操场奔跑，远处有彩虹" /><span className="studio-field__bottom"><button type="button" disabled={polishing} onClick={onPolish}>{polishing ? "润色中…" : "✨ 帮我润色"}</button><small>{hint.length}/120</small></span></label></>; }
function PresetChips({ label, presets, selected, onSelect, visual = false }: { label: string; presets: string[]; selected: string; onSelect: (preset: string) => void; visual?: boolean }) { return <div className={visual ? "studio-presets studio-presets--visual" : "studio-presets"}><h3>{label}</h3><div>{presets.map((preset, index) => { const example = STYLE_EXAMPLES[preset]; return <button type="button" key={preset} className={selected === preset ? "selected" : ""} onClick={() => onSelect(preset)}>{visual && <i className={`studio-style-thumb studio-style-thumb--${index}`} aria-hidden="true"><span>{example?.icon ?? "✦"}</span></i>}<b>{preset}</b>{visual && <em>{example?.hint ?? "示例风格"}</em>}</button>; })}</div></div>; }

function MediaPreview({ work, source }: { work: CreativeWork; source: string }) {
  const [playbackError, setPlaybackError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [coverError, setCoverError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const retryPlayback = () => { setPlaybackError(false); setReloadKey((current) => current + 1); };
  const downloadVideoCover = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) { setCoverError(true); return; }
    try {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("canvas unavailable");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const link = document.createElement("a");
      link.download = `${safeDownloadName(work.title)}-封面.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      setCoverError(false);
    } catch { setCoverError(true); }
  };
  if (!work.previewUrl) return null;
  if (!source) return <p role="status">正在安全加载作品…</p>;
  if (work.kind === "image") return <img className="studio-media-preview" src={source} alt={work.title} />;
  if (work.kind === "video") return <div><video ref={videoRef} key={reloadKey} className="studio-media-preview" controls autoPlay muted playsInline onError={() => setPlaybackError(true)} src={source}>你的浏览器暂不支持播放视频。</video><div className="studio-media-actions"><button type="button" onClick={downloadVideoCover}><Download size={16} /> 下载封面</button></div>{coverError && <p role="alert">当前画面还没准备好，播放视频后再试一次。</p>}{playbackError && <p role="alert">视频暂时无法播放。<button type="button" onClick={retryPlayback}>重新加载</button></p>}</div>;
  if (work.kind === "music" || work.kind === "text") return <div className="studio-player"><div className="studio-player__meta"><strong>🎵 {work.title}</strong>{work.durationSeconds ? <span>{work.durationSeconds} 秒</span> : null}</div><audio key={reloadKey} className="studio-audio-preview" controls onError={() => setPlaybackError(true)} src={source}>你的浏览器暂不支持播放音频。</audio>{playbackError && <p role="alert">歌曲暂时无法播放。<button type="button" onClick={retryPlayback}>重新加载</button></p>}{work.lyrics ? <details open className="studio-player__lyrics"><summary>查看歌词</summary><pre>{work.lyrics}</pre></details> : <p className="studio-player__empty">这首歌暂未返回歌词。</p>}</div>;
  return null;
}
