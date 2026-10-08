export type CreativeHouse = {
  id: "chat" | "html" | "image" | "music" | "video" | "agents";
  label: string;
  hint: string;
  href: string;
  icon: string;
  color: string;
  position: string;
  scenePosition: [number, number, number];
};

export const creativeHouses: CreativeHouse[] = [
  { id: "chat", label: "AI 对话", hint: "说说你的想法", href: "/workspace/chat", icon: "✦", color: "#62b8ff", position: "kids-house-link--chat", scenePosition: [-3.05, 0.6, -1.1] },
  { id: "html", label: "网页创作", hint: "造一个小网页", href: "/workspace/html", icon: "⌘", color: "#a485f7", position: "kids-house-link--html", scenePosition: [-0.8, 0.65, -1.85] },
  { id: "image", label: "图片创作", hint: "画出脑海画面", href: "/workspace/image", icon: "◉", color: "#ff8fab", position: "kids-house-link--image", scenePosition: [2.5, 0.56, -1.3] },
  { id: "music", label: "音乐创作", hint: "写一首新歌", href: "/workspace/music", icon: "♫", color: "#ffbd65", position: "kids-house-link--music", scenePosition: [-2.9, 0.62, 1.55] },
  { id: "video", label: "视频创作", hint: "让故事动起来", href: "/workspace/video", icon: "▶", color: "#62d8b4", position: "kids-house-link--video", scenePosition: [0.7, 0.62, 1.72] },
  { id: "agents", label: "智能体中心", hint: "选一位 AI 伙伴", href: "/agents", icon: "✺", color: "#f29bff", position: "kids-house-link--agents", scenePosition: [3.0, 0.66, 1.2] },
];
