"use client";

import { useEffect, useMemo, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AvailableProviderModel, currentSession, deleteProvider, listAvailableProviderModels, listModelCalls, listProviders, ModelCallRecord, ProviderSummary, registerProvider, testProvider } from "../../../src/api-client";

type Capability = "text" | "image" | "video" | "music";
type ConfigurationMode = "preset" | "custom";
type ConnectionState = "idle" | "testing" | "success" | "verification_required" | "failure";
type ProviderDraft = { providerId: string; providerKind: string; modelId: string; apiKey: string; baseUrl: string; enabled: boolean; modelCatalog: string[] };
type ModelOption = { id: string; name: string };
type ProviderPreset = { group: string; label: string; providerKind: string; modelId: string; baseUrl: string; hint: string; catalog?: ModelOption[]; requiresEndpoint?: boolean };

const meta: Record<Capability, { label: string; shortLabel: string; icon: string; description: string; color: string }> = {
  text: { label: "文字模型", shortLabel: "文字", icon: "文", description: "对话、写作、网页 Vibe Coding 和智能体思考", color: "violet" },
  image: { label: "图片模型", shortLabel: "图片", icon: "图", description: "海报、插画、角色和视觉素材生成", color: "rose" },
  video: { label: "视频模型", shortLabel: "视频", icon: "影", description: "短视频、分镜和动态故事生成", color: "amber" },
  music: { label: "音乐模型", shortLabel: "音乐", icon: "音", description: "歌词、旋律、背景音乐与歌曲灵感生成", color: "cyan" },
};

const catalogs = {
  tokenHubText: ["hy4-preview", "hy3", "hunyuan-2.0-instruct", "hunyuan-2.0-thinking", "hunyuan-role", "deepseek-v4-pro-202606", "deepseek-v4-pro", "deepseek-v4-flash-202605"].map((id) => ({ id, name: id })),
  qwenText: ["qwen3.8-max", "qwen3.8-flash", "qwen3.7-max", "qwen3.7-plus", "qwen3.7-flash", "qwen3.6-plus", "qwen3.6-flash", "qwen3.5-plus", "qwen3.5-flash", "qwen-plus", "qwen-turbo"].map((id) => ({ id, name: id })),
  deepSeekText: ["deepseek-chat", "deepseek-reasoner", "deepseek-v3.2", "deepseek-v4-pro", "deepseek-v4-flash"].map((id) => ({ id, name: id })),
  zhipuText: ["glm-5.2", "glm-5.1", "glm-5", "glm-4-plus", "glm-4-flash", "glm-4-long"].map((id) => ({ id, name: id })),
  kimiText: ["kimi-k3", "kimi-k2.7-code", "kimi-k2.6", "kimi-k2.5", "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"].map((id) => ({ id, name: id })),
  miniMaxText: ["MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-Text-01"].map((id) => ({ id, name: id })),
  baiduText: ["ernie-4.5-turbo-128k", "ernie-4.5-turbo-vl-32k", "ernie-4.0-turbo-8k", "ernie-speed-128k"].map((id) => ({ id, name: id })),
  siliconFlowText: ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen3-32B", "Qwen/Qwen3-235B-A22B"].map((id) => ({ id, name: id })),
  ppioText: ["deepseek/deepseek-v3-0324", "deepseek/deepseek-r1", "qwen/qwen3-32b", "qwen/qwen2.5-72b-instruct"].map((id) => ({ id, name: id })),
  hunyuanText: ["hunyuan-turbos-latest", "hunyuan-large", "hunyuan-standard-256k", "hunyuan-vision"].map((id) => ({ id, name: id })),
  stepFunText: ["step-2-mini", "step-1-8k", "step-1-32k", "step-1-256k"].map((id) => ({ id, name: id })),
  sparkText: ["spark-x1", "spark-max", "spark-pro", "spark-lite"].map((id) => ({ id, name: id })),
  baichuanText: ["Baichuan4", "Baichuan3-Turbo", "Baichuan2-Turbo"].map((id) => ({ id, name: id })),
  yiText: ["yi-lightning", "yi-large", "yi-medium"].map((id) => ({ id, name: id })),
  senseNovaText: ["SenseChat-5", "SenseChat-Turbo", "SenseChat-Vision"].map((id) => ({ id, name: id })),
  mimoText: ["mimo-v2-flash", "mimo-v2-pro", "mimo-v1"].map((id) => ({ id, name: id })),
  qwenImage: ["qwen-image-3.0-pro", "qwen-image-3.0", "qwen-image-2.0-pro", "qwen-image-2.0", "wan2.7-image-pro", "wan2.7-image", "wan2.6-t2i", "wan2.6-image", "wan2.2-t2i-plus", "wan2.2-t2i-flash"].map((id) => ({ id, name: id })),
  qwenVideo: ["wan2.6-t2v", "wan2.6-i2v", "wan2.5-t2v-preview", "wan2.5-i2v-preview", "wan2.2-t2v-plus", "wan2.2-i2v-plus", "wanx2.1-t2v-plus"].map((id) => ({ id, name: id })),
  doubaoImage: ["doubao-seedream-5-0-pro-260628", "doubao-seedream-5-0-flash-260915", "doubao-seedream-5-0-260128", "doubao-seedream-4-5-251128", "doubao-seedream-4-0-20260415"].map((id) => ({ id, name: `${id}（需使用你的 Endpoint ID）` })),
  doubaoVideo: ["doubao-seedance-2-5-260628", "doubao-seedance-2-0-260128", "doubao-seedance-2-0-fast-260128", "doubao-seedance-2-0-mini-260615", "doubao-seedance-1-5-pro-251215"].map((id) => ({ id, name: `${id}（需使用你的 Endpoint ID）` })),
  qwenMusic: ["fun-music-v1", "fun-music-preview"].map((id) => ({ id, name: id })),
  doubaoMusic: ["doubao-seedmusic-1-0", "doubao-seedmusic-1-5-pro", "doubao-seedmusic-1-5-lite"].map((id) => ({ id, name: `${id}（需使用你的 Endpoint ID）` })),
  klingMusic: ["kling-music-v1", "kling-music-pro"].map((id) => ({ id, name: id })),
  miniMaxMusic: ["music-01", "music-02", "music-03"].map((id) => ({ id, name: id })),
};

const presets: Record<Capability, ProviderPreset[]> = {
  text: [
    { group: "国内模型平台", label: "火山方舟（豆包及第三方模型）", providerKind: "doubao", modelId: "doubao-seed-2-1-pro-260628", baseUrl: "https://ark.cn-beijing.volces.com/api/v3", hint: "已填入方舟地址和推荐文字模型；也可替换为你的 Endpoint ID。", catalog: [{ id: "doubao-seed-2-1-pro-260628", name: "doubao-seed-2-1-pro-260628" }, { id: "doubao-seed-2-1-lite-260628", name: "doubao-seed-2-1-lite-260628" }] },
    { group: "国内模型平台", label: "阿里云百炼（通义及第三方模型）", providerKind: "qwen", modelId: "qwen-plus", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", hint: "已填入北京地域的 OpenAI 兼容地址和推荐模型，可在保存后刷新最新模型。", catalog: catalogs.qwenText },
    { group: "国内模型平台", label: "腾讯云 TokenHub", providerKind: "custom", modelId: "hy4-preview", baseUrl: "https://tokenhub.tencentmaas.com/v1", hint: "已填入中国大陆 OpenAI 兼容地址和混元推荐模型，可在保存后刷新可用模型。", catalog: catalogs.tokenHubText },
    { group: "国内模型平台", label: "百度智能云千帆 ModelBuilder", providerKind: "custom", modelId: "ernie-4.5-turbo-128k", baseUrl: "", hint: "内置千帆常用模型目录；兼容接口地址以你的千帆控制台为准。", catalog: catalogs.baiduText },
    { group: "国内模型平台", label: "硅基流动 SiliconFlow", providerKind: "custom", modelId: "deepseek-ai/DeepSeek-V3", baseUrl: "", hint: "内置硅基流动常用开源模型目录；Base URL 以控制台为准。", catalog: catalogs.siliconFlowText },
    { group: "国内模型平台", label: "PPIO 派欧云", providerKind: "custom", modelId: "deepseek/deepseek-v3-0324", baseUrl: "", hint: "内置 PPIO 常用模型目录；Base URL 以控制台为准。", catalog: catalogs.ppioText },
    { group: "国内自研模型", label: "深度求索 DeepSeek", providerKind: "deepseek", modelId: "deepseek-chat", baseUrl: "https://api.deepseek.com", hint: "适合对话、写作和网页 Vibe Coding；保存后可刷新服务商最新模型。", catalog: catalogs.deepSeekText },
    { group: "国内自研模型", label: "腾讯混元", providerKind: "custom", modelId: "hunyuan-turbos-latest", baseUrl: "https://api.hunyuan.cloud.tencent.com/v1", hint: "内置混元常用模型目录，实际可用模型取决于账号权限。", catalog: catalogs.hunyuanText },
    { group: "国内自研模型", label: "通义千问（直连百炼）", providerKind: "qwen", modelId: "qwen-plus", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", hint: "已填入北京地域的 OpenAI 兼容地址和推荐模型。", catalog: catalogs.qwenText },
    { group: "国内自研模型", label: "智谱 AI GLM", providerKind: "zhipu", modelId: "glm-5.2", baseUrl: "https://open.bigmodel.cn/api/paas/v4", hint: "内置 GLM 常用模型目录，实际可用模型取决于你的账号权限。", catalog: catalogs.zhipuText },
    { group: "国内自研模型", label: "Kimi（月之暗面）", providerKind: "custom", modelId: "kimi-k3", baseUrl: "", hint: "内置 Kimi 常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.kimiText },
    { group: "国内自研模型", label: "MiniMax", providerKind: "custom", modelId: "MiniMax-M2.5", baseUrl: "", hint: "内置 MiniMax 常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.miniMaxText },
    { group: "国内自研模型", label: "阶跃星辰 StepFun", providerKind: "custom", modelId: "step-2-mini", baseUrl: "", hint: "内置阶跃星辰常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.stepFunText },
    { group: "国内自研模型", label: "讯飞星火", providerKind: "custom", modelId: "spark-x1", baseUrl: "", hint: "内置讯飞星火常用模型目录；HTTP 兼容地址以控制台为准。", catalog: catalogs.sparkText },
    { group: "国内自研模型", label: "百川智能", providerKind: "custom", modelId: "Baichuan4", baseUrl: "", hint: "内置百川常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.baichuanText },
    { group: "国内自研模型", label: "零一万物 Yi", providerKind: "custom", modelId: "yi-lightning", baseUrl: "", hint: "内置 Yi 常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.yiText },
    { group: "国内自研模型", label: "商汤日日新 SenseNova", providerKind: "custom", modelId: "SenseChat-5", baseUrl: "", hint: "内置商汤常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.senseNovaText },
    { group: "国内自研模型", label: "小米 MiMo", providerKind: "custom", modelId: "mimo-v2-flash", baseUrl: "", hint: "内置小米 MiMo 常用模型目录；Base URL 以开放平台控制台为准。", catalog: catalogs.mimoText },
  ],
  image: [
    { group: "国内模型平台", label: "火山方舟（豆包图像）", providerKind: "doubao", modelId: "doubao-seedream-4-0-20260415", baseUrl: "https://ark.cn-beijing.volces.com/api/v3", hint: "内置豆包图像模型目录；实际调用时请使用对应模型创建的 Endpoint ID。", catalog: catalogs.doubaoImage, requiresEndpoint: true },
    { group: "国内模型平台", label: "阿里云百炼（通义万相）", providerKind: "qwen", modelId: "qwen-image-3.0-pro", baseUrl: "https://dashscope.aliyuncs.com/api/v1", hint: "已填入百炼原生 API 地址和图像模型目录。", catalog: catalogs.qwenImage },
    { group: "国内模型平台", label: "腾讯云 TokenHub", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写 TokenHub 控制台提供的图像模型接口配置。" },
    { group: "国内模型平台", label: "百度智能云千帆", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写千帆控制台提供的图像模型接口配置。" },
    { group: "国内模型平台", label: "硅基流动 SiliconFlow", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写硅基流动控制台提供的图像模型接口配置。" },
    { group: "国内自研模型", label: "腾讯混元图像", providerKind: "custom", modelId: "", baseUrl: "https://api.hunyuan.cloud.tencent.com/v1", hint: "填写已开通的混元图像模型名称。" },
    { group: "国内自研模型", label: "智谱 CogView", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写智谱开放平台提供的图像模型接口配置。" },
    { group: "国内自研模型", label: "MiniMax 图像", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写 MiniMax 开放平台提供的图像模型接口配置。" },
    { group: "国内自研模型", label: "阶跃星辰图像", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写阶跃星辰开放平台提供的图像模型接口配置。" },
  ],
  video: [
    { group: "国内模型平台", label: "火山方舟（Seedance / 豆包视频）", providerKind: "doubao", modelId: "doubao-seedance-2-0-260128", baseUrl: "https://ark.cn-beijing.volces.com/api/v3", hint: "内置 Seedance 视频模型目录；实际调用时请使用对应模型创建的 Endpoint ID。", catalog: catalogs.doubaoVideo, requiresEndpoint: true },
    { group: "国内模型平台", label: "阿里云百炼（通义万相视频）", providerKind: "qwen", modelId: "wan2.6-t2v", baseUrl: "https://dashscope.aliyuncs.com/api/v1", hint: "已填入百炼原生 API 地址和视频模型目录。", catalog: catalogs.qwenVideo },
    { group: "国内模型平台", label: "腾讯云 TokenHub", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写 TokenHub 控制台提供的视频模型接口配置。" },
    { group: "国内模型平台", label: "百度智能云千帆", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写千帆控制台提供的视频模型接口配置。" },
    { group: "国内模型平台", label: "硅基流动 SiliconFlow", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写硅基流动控制台提供的视频模型接口配置。" },
    { group: "国内自研模型", label: "腾讯混元视频", providerKind: "custom", modelId: "", baseUrl: "https://api.hunyuan.cloud.tencent.com/v1", hint: "填写已开通的混元视频模型名称。" },
    { group: "国内自研模型", label: "可灵 AI Kling", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写可灵开放平台提供的视频模型接口配置。" },
    { group: "国内自研模型", label: "智谱 CogVideo", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写智谱开放平台提供的视频模型接口配置。" },
    { group: "国内自研模型", label: "MiniMax 视频", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写 MiniMax 开放平台提供的视频模型接口配置。" },
    { group: "国内自研模型", label: "阶跃星辰视频", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写阶跃星辰开放平台提供的视频模型接口配置。" },
  ],
  music: [
    { group: "国内模型平台", label: "火山方舟（豆包音乐 / SeedMusic）", providerKind: "doubao", modelId: "doubao-seedmusic-1-0", baseUrl: "https://ark.cn-beijing.volces.com/api/v3", hint: "已填入方舟音乐接口地址和推荐模型；实际调用时请使用对应模型创建的 Endpoint ID。", catalog: catalogs.doubaoMusic, requiresEndpoint: true },
    { group: "国内模型平台", label: "阿里云百炼（通义万相音乐）", providerKind: "qwen", modelId: "fun-music-v1", baseUrl: "https://dashscope.aliyuncs.com/api/v1", hint: "Fun-Music 需先在百炼申请邀测开通；默认地址和模型可一键填入。", catalog: catalogs.qwenMusic },
    { group: "国内自研模型", label: "可灵 AI Kling 音乐", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写可灵开放平台提供的音乐模型接口配置。", catalog: catalogs.klingMusic },
    { group: "国内自研模型", label: "MiniMax 海螺音乐", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写 MiniMax 开放平台提供的音乐模型接口配置。", catalog: catalogs.miniMaxMusic },
    { group: "国内自研模型", label: "腾讯混元音乐", providerKind: "custom", modelId: "", baseUrl: "https://api.hunyuan.cloud.tencent.com/v1", hint: "填写已开通的混元音乐模型名称。" },
    { group: "国内自研模型", label: "智谱音乐", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写智谱开放平台提供的音乐模型接口配置。" },
    { group: "国内自研模型", label: "阶跃星辰音乐", providerKind: "custom", modelId: "", baseUrl: "", hint: "填写阶跃星辰开放平台提供的音乐模型接口配置。" },
  ],
};

const emptyDraft = (capability: Capability, slot: number): ProviderDraft => ({ providerId: `${capability}-${slot}`, providerKind: "", modelId: "", apiKey: "", baseUrl: "", enabled: true, modelCatalog: [] });
const draftForPreset = (capability: Capability, slot: number, presetIndex = 0): ProviderDraft => {
  const preset = presets[capability][presetIndex];
  return { ...emptyDraft(capability, slot), providerKind: preset.providerKind, modelId: preset.modelId, baseUrl: preset.baseUrl, modelCatalog: preset.modelId ? [preset.modelId] : [] };
};
const roleLabels = ["主模型", "备用模型", "兜底模型"];

export default function ProvidersAdminPage() {
  const [capability, setCapability] = useState<Capability>("text");
  const [selectedSlot, setSelectedSlot] = useState(0);
  const [mode, setMode] = useState<ConfigurationMode>("preset");
  const [selectedPreset, setSelectedPreset] = useState(0);
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [calls, setCalls] = useState<ModelCallRecord[]>([]);
  const [availableModels, setAvailableModels] = useState<AvailableProviderModel[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isQuickConfiguring, setIsQuickConfiguring] = useState(false);
  const [manualModelMode, setManualModelMode] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [draft, setDraft] = useState<ProviderDraft>(emptyDraft("text", 1));
  const [status, setStatus] = useState("");
  const activeProviders = useMemo(() => providers.filter((provider) => provider.capability === capability).sort((left, right) => left.priority - right.priority), [providers, capability]);
  const presetGroups = useMemo(() => presets[capability].reduce<Record<string, Array<{ preset: ProviderPreset; index: number }>>>((groups, preset, index) => {
    groups[preset.group] = [...(groups[preset.group] ?? []), { preset, index }];
    return groups;
  }, {}), [capability]);
  const chosen = activeProviders[selectedSlot];
  const activePreset = presets[capability][selectedPreset] ?? presets[capability][0];
  const usesRecommendedModel = Boolean(activePreset.modelId && draft.modelId === activePreset.modelId);
  const modelOptions = useMemo(() => {
    const options = [
      ...(activePreset.catalog ?? []),
      ...(activePreset.modelId ? [{ id: activePreset.modelId, name: `推荐模型 · ${activePreset.modelId}` }] : []),
      ...draft.modelCatalog.map((id) => ({ id, name: `已保存模型 · ${id}` })),
      ...availableModels,
      ...(draft.modelId && draft.modelId !== activePreset.modelId && !availableModels.some((model) => model.id === draft.modelId) ? [{ id: draft.modelId, name: `当前配置 · ${draft.modelId}` }] : []),
    ];
    return Array.from(new Map(options.map((model) => [model.id, model])).values());
  }, [activePreset.catalog, activePreset.modelId, availableModels, draft.modelCatalog, draft.modelId]);
  const configuredCount = (kind: Capability) => providers.filter((provider) => provider.capability === kind && provider.enabled).length;

  const refresh = async () => {
    const session = currentSession();
    if (!session) return;
    const [nextProviders, nextCalls] = await Promise.all([listProviders(session.accessToken), listModelCalls(session.accessToken)]);
    setProviders(nextProviders);
    setCalls(nextCalls);
  };

  useEffect(() => { void refresh().catch(() => setStatus("暂时无法读取服务端配置或调用记录。")); }, []);
  useEffect(() => {
    const provider = activeProviders[selectedSlot];
    setDraft(provider ? { providerId: provider.provider_id, providerKind: provider.provider_kind, modelId: provider.model_id, apiKey: "", baseUrl: provider.base_url, enabled: provider.enabled, modelCatalog: provider.model_catalog ?? [] } : draftForPreset(capability, selectedSlot + 1));
    const matchingPresetIndex = provider ? presets[capability].findIndex((preset) => preset.providerKind === provider.provider_kind && preset.baseUrl === provider.base_url) : 0;
    setSelectedPreset(matchingPresetIndex >= 0 ? matchingPresetIndex : 0);
    setAvailableModels([]);
    setConnectionState("idle");
    setMode(provider?.provider_kind === "custom" ? "custom" : "preset");
    setManualModelMode(false);
  }, [capability, selectedSlot, providers]);

  function chooseCapability(next: Capability) { setCapability(next); setSelectedSlot(0); setStatus(""); }
  function updateDraft(next: Partial<ProviderDraft>) {
    setDraft((current) => ({ ...current, ...next }));
    setConnectionState("idle");
  }
  function applyPreset(index: number) {
    const preset = presets[capability][index];
    setSelectedPreset(index);
    setManualModelMode(false);
    updateDraft({ providerKind: preset.providerKind, modelId: preset.modelId, baseUrl: preset.baseUrl, modelCatalog: preset.modelId ? [preset.modelId] : [] });
    setStatus(`已填入 ${preset.label} 的服务商类型、推荐模型和 Base URL；只需补充 API Key。`);
  }
  function applyRecommendedModel() {
    if (!activePreset.modelId) return setStatus("该服务商需要在控制台创建 Endpoint ID，请将 Endpoint ID 粘贴到模型名称栏。");
    if (draft.modelId === activePreset.modelId) return setStatus(`当前已使用推荐模型：${activePreset.modelId}。`);
    setManualModelMode(false);
    updateDraft({ modelId: activePreset.modelId });
    setStatus(`已一键填入推荐模型：${activePreset.modelId}。`);
  }
  function addManualModel() {
    const modelId = draft.modelId.trim();
    if (!modelId) return setStatus(activePreset.requiresEndpoint ? "请先粘贴 Endpoint ID。" : "请先输入模型名称。");
    updateDraft({ modelCatalog: Array.from(new Set([...draft.modelCatalog, modelId])) });
    setManualModelMode(false);
    setStatus(`已加入下拉列表：${modelId}。点击“确认配置”后会永久保存。`);
  }
  async function refreshAvailableModels() {
    const session = currentSession();
    if (!session || !chosen) return setStatus("请先保存该 API 配置，再刷新服务商的最新模型列表。");
    setIsDiscovering(true);
    try {
      const models = await listAvailableProviderModels(session.accessToken, chosen.provider_id);
      const modelCatalog = Array.from(new Set([...draft.modelCatalog, ...models.map((model) => model.id)]));
      await registerProvider(session.accessToken, { providerId: draft.providerId, capability, region: "domestic", providerKind: draft.providerKind, modelId: draft.modelId, baseUrl: draft.baseUrl, priority: selectedSlot + 1, enabled: draft.enabled, modelCatalog });
      setAvailableModels(models);
      setDraft((current) => ({ ...current, modelCatalog }));
      await refresh();
      setStatus(`已一键更新并保存 ${models.length} 个服务商模型；打开下拉即可选择。`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "刷新模型列表失败。"); }
    finally { setIsDiscovering(false); }
  }
  async function persistProvider(): Promise<string> {
    const session = currentSession();
    if (!session) throw new Error("请先使用平台管理员账号登录。");
    if (!draft.providerId.trim() || !draft.modelId.trim() || !draft.baseUrl.trim() || (!draft.apiKey.trim() && !chosen?.api_key)) throw new Error("请填写模型名称和 Base URL；首次保存还需要 API Key。");
    const providerId = draft.providerId.trim();
    await registerProvider(session.accessToken, { providerId, capability, region: "domestic", ...(draft.apiKey.trim() ? { apiKey: draft.apiKey.trim() } : {}), providerKind: draft.providerKind.trim() || "custom", modelId: draft.modelId.trim(), baseUrl: draft.baseUrl.trim(), priority: selectedSlot + 1, enabled: draft.enabled, modelCatalog: Array.from(new Set([...draft.modelCatalog, draft.modelId.trim()])).filter(Boolean) });
    setDraft((value) => ({ ...value, apiKey: "" }));
    await refresh();
    return providerId;
  }
  async function save() {
    try {
      await persistProvider();
      setConnectionState("idle");
      setStatus(`${roleLabels[selectedSlot]}已加密保存，会按“主用 → 备用 → 兜底”顺序自动降级。`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "保存失败。"); }
  }
  async function quickConfigure() {
    const session = currentSession();
    if (!session) return setStatus("请先使用平台管理员账号登录。");
    setIsQuickConfiguring(true);
    setConnectionState("testing");
    setStatus("正在保存配置并发起最小连通测试…");
    try {
      const providerId = await persistProvider();
      const result = await testProvider(session.accessToken, providerId);
      setConnectionState(result.status === "connected" ? "success" : "verification_required");
      setStatus(result.message || "配置已保存，请进行一次实际生成验证。 ");
    } catch (error) {
      setConnectionState("failure");
      setStatus(error instanceof Error ? error.message : "保存或连接测试失败。");
    } finally { setIsQuickConfiguring(false); }
  }
  async function remove() {
    const session = currentSession();
    if (!session || !chosen) return setStatus("当前调度位还没有已保存的配置。");
    try { await deleteProvider(session.accessToken, chosen.provider_id); await refresh(); setStatus("该模型已从自动调用队列移除。"); } catch { setStatus("删除失败。"); }
  }
  async function testConnection() {
    const session = currentSession();
    if (!session || !chosen) return setStatus("请先保存该模型配置。");
    setConnectionState("testing");
    setStatus("正在向服务商发起安全连通测试…");
    try {
      const result = await testProvider(session.accessToken, chosen.provider_id);
      setConnectionState(result.status === "connected" ? "success" : result.status === "verification_required" ? "verification_required" : "failure");
      setStatus(result.message || "连接测试未通过，请检查当前配置。");
    } catch (error) {
      setConnectionState("failure");
      setStatus(error instanceof Error ? error.message : "连接测试失败，请检查 API Key、模型名称和接口地址后再试。");
    }
  }

  return <AdminShell active="/admin/providers"><main className="admin-page model-hub">
    <header className="model-hub__heading">
      <div><p className="admin-eyebrow">AI CAPABILITY CENTER</p><h1>AI 能力中心</h1><p>按能力独立配置模型。每种能力最多 3 个 API，系统会在额度不足或请求失败时自动切换。</p></div>
      <a className="model-hub__log-link" href="#model-call-log">查看调用记录 →</a>
    </header>

    <section className="model-summary" aria-label="已配置模型">
      <div className="model-summary__title"><div><h2>已配置模型</h2><p>主模型会优先调用；未配置时学生无法使用对应创作能力。</p></div><span>自动调度已开启</span></div>
      <div className="model-summary__grid">{(Object.keys(meta) as Capability[]).map((item) => {
        const primary = providers.filter((provider) => provider.capability === item).sort((left, right) => left.priority - right.priority)[0];
        return <button type="button" className={`model-summary__item ${capability === item ? "is-active" : ""}`} onClick={() => chooseCapability(item)} key={item}>
          <span className={`model-summary__icon model-summary__icon--${meta[item].color}`}>{meta[item].icon}</span>
          <span><b>{meta[item].label}</b><small>{primary ? `${primary.provider_kind} · ${primary.model_id}` : "尚未配置"}</small></span>
          <em>{configuredCount(item) ? `${configuredCount(item)} / 3 已启用` : "待配置"}</em>
        </button>;
      })}</div>
    </section>

    <section className="model-workbench">
      <nav className="model-workbench__tabs" aria-label="模型能力分类">{(Object.keys(meta) as Capability[]).map((item) => <button type="button" className={capability === item ? "is-active" : ""} onClick={() => chooseCapability(item)} key={item}><span>{meta[item].icon}</span>{meta[item].label}<small>{configuredCount(item)} / 3</small></button>)}</nav>
      <div className="model-workbench__body">
        <aside className="model-slots">
          <div className="model-slots__intro"><span className={`model-slots__icon model-slots__icon--${meta[capability].color}`}>{meta[capability].icon}</span><div><h2>{meta[capability].label}</h2><p>{meta[capability].description}</p></div></div>
          {[0, 1, 2].map((slot) => {
            const provider = activeProviders[slot];
            return <button type="button" className={`model-slot ${selectedSlot === slot ? "is-selected" : ""}`} onClick={() => setSelectedSlot(slot)} key={slot}>
              <span className={`model-slot__number model-slot__number--${slot + 1}`}>{slot + 1}</span><span className="model-slot__copy"><b>{roleLabels[slot]}</b><strong>{provider?.provider_kind || "添加模型"}</strong><small>{provider?.model_id || "选择服务商后配置"}</small></span><em className={provider?.enabled ? "is-ready" : ""}>{provider?.enabled ? "已启用" : provider ? "已停用" : "未配置"}</em>
            </button>;
          })}
          <div className="model-slots__rule"><b>自动降级规则</b><p>主模型不可用时，自动尝试下一个已启用模型。</p></div>
        </aside>

        <section className="model-editor">
          <header className="model-editor__heading"><div><p>配置 {selectedSlot + 1} · {roleLabels[selectedSlot]}</p><h2>{chosen ? chosen.provider_kind : `添加${roleLabels[selectedSlot]}`}</h2></div><span className={draft.enabled ? "model-state model-state--ready" : "model-state"}>{draft.enabled ? "● 已启用" : "○ 已停用"}</span></header>
          <div className="model-editor__mode"><button type="button" className={mode === "preset" ? "is-active" : ""} onClick={() => setMode("preset")}>服务商预设</button><button type="button" className={mode === "custom" ? "is-active" : ""} onClick={() => setMode("custom")}>自定义 API</button></div>
          {mode === "preset" && <section className="provider-preset-picker"><label>模型服务商<select value={selectedPreset} onChange={(event) => applyPreset(Number(event.target.value))}>{Object.entries(presetGroups).map(([group, options]) => <optgroup label={group} key={group}>{options.map(({ preset, index }) => <option value={index} key={preset.label}>{preset.label}</option>)}</optgroup>)}</select></label><div className="provider-preset-picker__hint"><p>{activePreset.hint}</p><button type="button" onClick={() => applyPreset(selectedPreset)}>一键填充类型、模型和 Base URL</button></div></section>}
          <div className="model-form-grid">
            {mode === "custom" && <label>配置标识<input value={draft.providerId} onChange={(event) => updateDraft({ providerId: event.target.value })} placeholder="例如：text-custom-1" /></label>}
            <label>服务商类型<input value={draft.providerKind} onChange={(event) => updateDraft({ providerKind: event.target.value })} placeholder="deepseek / doubao / qwen / custom" /></label>
            <label>模型名称<div className="model-picker"><select value={manualModelMode ? "__manual__" : draft.modelId} onChange={(event) => { if (event.target.value === "__manual__") { setManualModelMode(true); return; } setManualModelMode(false); updateDraft({ modelId: event.target.value }); }}><option value="" disabled>请选择模型</option>{modelOptions.length > 0 && <optgroup label="内置 / 已保存模型">{modelOptions.map((model) => <option value={model.id} key={model.id}>{model.name}</option>)}</optgroup>}<option value="__manual__">{activePreset.requiresEndpoint ? "手动填写 Endpoint ID" : "手动添加模型名称"}</option></select><button type="button" disabled={!chosen || isDiscovering} onClick={() => void refreshAvailableModels()}>{isDiscovering ? "更新中…" : "一键更新模型列表"}</button></div>{manualModelMode && <div className="manual-model-entry"><input value={draft.modelId} onChange={(event) => updateDraft({ modelId: event.target.value })} placeholder={activePreset.requiresEndpoint ? "粘贴服务商控制台创建的 Endpoint ID" : "请输入服务商提供的模型名称"} /><button type="button" onClick={addManualModel}>加入下拉列表</button></div>}</label>
            <label className="model-form-grid__wide">API Key <span>仅加密保存，不会再次显示</span><input type="password" value={draft.apiKey} onChange={(event) => updateDraft({ apiKey: event.target.value })} placeholder={chosen?.api_key || "请输入 API Key"} autoComplete="new-password" /></label>
            <label className="model-form-grid__wide">Base URL<input value={draft.baseUrl} placeholder="服务商 API 地址" onChange={(event) => updateDraft({ baseUrl: event.target.value })} /></label>
          </div>
          <div className="model-options"><label><input type="checkbox" checked={draft.enabled} onChange={(event) => updateDraft({ enabled: event.target.checked })} /> 启用此模型</label><span>保存后将按当前顺序加入自动调用队列</span></div>
          <div className="model-fallback"><div><b>当前{meta[capability].shortLabel}能力的调用顺序</b><p>{activeProviders.length ? activeProviders.map((provider, index) => `${index + 1}. ${provider.provider_kind}`).join("   →   ") : "从主模型开始添加，最多可配置 3 个。"}</p></div><span>额度 / 故障自动切换</span></div>
          <div className="model-editor__actions"><button className={`admin-button--quiet model-connection-button ${connectionState === "success" ? "is-success" : connectionState === "verification_required" ? "is-warning" : ""}`} type="button" disabled={!chosen || connectionState === "testing"} onClick={() => void testConnection()}>{connectionState === "testing" ? "连接测试中…" : connectionState === "success" ? "✓ 测试成功" : connectionState === "verification_required" ? "需实际生成验证" : "检测模型状态"}</button><button className="admin-button--quiet model-editor__delete" type="button" disabled={!chosen} onClick={() => void remove()}>删除</button><button className="admin-button--quiet" type="button" disabled={isQuickConfiguring} onClick={() => void quickConfigure()}>{isQuickConfiguring ? "配置测试中…" : "保存并测试"}</button><button className="admin-primary-button" type="button" onClick={() => void save()}>确认配置</button></div>
          {status && <div className={connectionState === "success" ? "model-connection-feedback is-success" : connectionState === "verification_required" ? "model-connection-feedback is-warning" : connectionState === "failure" ? "model-connection-feedback is-failure" : "admin-feedback"}>{connectionState === "success" && <span>✓</span>}{connectionState === "verification_required" && <span>i</span>}{connectionState === "failure" && <span>!</span>}{status}</div>}
          <p className="model-editor__security">安全说明：学生与老师不会接触 API Key，密钥只以加密形式保存在服务端。</p>
        </section>
      </div>
    </section>

    <section className="admin-panel provider-log" id="model-call-log"><div className="admin-panel-heading"><div><h2>最近调用与自动切换</h2><p>显示真实模型调用记录，用于定位异常、额度用尽和降级情况。</p></div><a href="/admin/quotas">查看额度 →</a></div><div className="admin-log-table"><div className="admin-log-head"><span>时间</span><span>能力</span><span>API 配置</span><span>结果</span><span>机构</span></div>{calls.length ? calls.map((call, index) => <div key={`${call.created_at}-${index}`}><span>{new Date(call.created_at).toLocaleString("zh-CN", { hour12: false })}</span><span>{call.capability}</span><span>{call.provider_id}</span><span className={call.outcome === "succeeded" ? "log-success" : "log-warning"}>{call.outcome}</span><span>{call.organization_id}</span></div>) : <div><span>暂无真实调用记录</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}</div></section>
  </main></AdminShell>;
}
