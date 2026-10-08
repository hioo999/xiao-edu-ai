export type StudentFeature =
  | "chat"
  | "html"
  | "image"
  | "music"
  | "video"
  | "expert-team"
  | "courses"
  | "projects";

export interface FeatureGate {
  id: StudentFeature;
  label: string;
  description: string;
  enabled: boolean;
}

export const studentFeatures: FeatureGate[] = [
  { id: "chat", label: "AI 文字", description: "和智能体对话，把想法说清楚。", enabled: true },
  { id: "html", label: "网页创作", description: "用自然语言设计、生成并预览网页。", enabled: true },
  { id: "image", label: "AI 图片", description: "把故事变成画面和海报。", enabled: true },
  { id: "music", label: "AI 音乐", description: "创作旋律、歌词和声音。", enabled: true },
  { id: "video", label: "AI 视频", description: "让画面和故事动起来。", enabled: true },
  { id: "expert-team", label: "智能体中心", description: "召集不同能力的智能体一起完成任务。", enabled: true },
  { id: "courses", label: "AI 课程", description: "跟着老师的步骤完成挑战。", enabled: true },
  { id: "projects", label: "我的项目", description: "查看并继续你的跨模态作品。", enabled: true },
];

export function getVisibleFeatures(features: FeatureGate[] = studentFeatures): FeatureGate[] {
  return features.filter((feature) => feature.enabled);
}

export function canEnterFeature(
  featureId: StudentFeature,
  features: FeatureGate[] = studentFeatures,
): boolean {
  return features.some((feature) => feature.id === featureId && feature.enabled);
}
