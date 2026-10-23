export type ShowcaseProjectType = "网页" | "图片" | "音乐" | "视频" | "文字";

export type ShowcaseProject = {
  id: string;
  title: string;
  student: string;
  type: ShowcaseProjectType;
  cover: string;
  description: string;
  process: string[];
  prompt: string;
  previewUrl?: string;
  featured?: boolean;
};

export const showcaseProjects: ShowcaseProject[] = [
  { id: "magic-book", title: "会发光的魔法书", student: "参考创意", type: "网页", cover: "linear-gradient(145deg, #7e8df5, #55d7e8 55%, #fff0a8)", description: "点开书页，星星会飞出来讲一个勇敢的小故事。", process: ["想象魔法书里的主角", "告诉 AI 要有点击互动", "预览后调整星星颜色"], prompt: "请帮我制作一本会翻页的魔法书网页，点击书页会飞出星星和一句鼓励的话。", featured: true },
  { id: "forest-castle", title: "云端森林城堡", student: "参考创意", type: "图片", cover: "linear-gradient(145deg, #7bd1a2, #b8f2d0 52%, #fff0a8)", description: "藏在大树和云朵里的城堡，有会说话的小松鼠。", process: ["选择儿童绘画风格", "加入森林和城堡细节", "调整成明亮的童话色彩"], prompt: "云端森林里的彩虹城堡，会说话的小松鼠守在门口，儿童绘本插画风格。", featured: true },
  { id: "forest-song", title: "森林精灵进行曲", student: "参考创意", type: "音乐", cover: "linear-gradient(145deg, #a98bf4, #ffb8d0 52%, #ffe18a)", description: "一首和小伙伴一起走进森林的快乐儿歌。", process: ["写下森林探险主题", "选择轻快节奏", "试听并修改副歌"], prompt: "创作一首关于森林精灵和好朋友探险的快乐儿童歌曲，副歌要简单好唱。" },
  { id: "magic-brush", title: "马良的神笔", student: "参考创意", type: "视频", cover: "linear-gradient(145deg, #ffaf91, #ffd36e 52%, #8fbdff)", description: "神笔画出一条小龙，小龙飞过校园送来彩虹。", process: ["把故事分成三个镜头", "描述主角和动作", "生成后挑选最喜欢的一段"], prompt: "神笔画出一条可爱的小龙，小龙飞过校园，在天空留下彩虹，明亮卡通短片。", previewUrl: "/samples/magic-brush.mp4", featured: true },
  { id: "moon-rabbit", title: "月球种花的小兔子", student: "参考创意", type: "图片", cover: "linear-gradient(145deg, #5d77db, #a9d9ff 54%, #ffe5a6)", description: "穿着宇航服的小兔子，在月球花园种下第一朵彩虹花。", process: ["确定兔子和月球场景", "加入花园与星空", "用柔和色彩完成画面"], prompt: "一只穿宇航服的小兔子在月球种彩虹花，童话绘本插画，柔和蓝紫色。" },
  { id: "rainbow-school", title: "彩虹校园小报", student: "参考创意", type: "文字", cover: "linear-gradient(145deg, #ff94a9, #ffc870 52%, #f8f4b7)", description: "一份介绍校园新发现的快乐小报，有标题、采访和小诗。", process: ["收集校园里的小发现", "用 AI 整理采访内容", "排版成温暖的小报"], prompt: "写一份小学三年级校园小报，主题是秋天校园的新发现，要有标题、采访和一首四行小诗。" },
  { id: "robot-garden", title: "机器人花园守护队", student: "参考创意", type: "网页", cover: "linear-gradient(145deg, #6ccfb0, #b6f1e5 52%, #e6ffad)", description: "点击不同花朵，机器人会说出它们的名字和照顾方法。", process: ["选定机器人守护花园主题", "设计可点击的花朵", "预览并修改提示文字"], prompt: "制作一个儿童互动网页：机器人守护花园，点击不同花朵会显示名称和照顾小提示。" },
  { id: "star-train", title: "星星列车去旅行", student: "参考创意", type: "视频", cover: "linear-gradient(145deg, #4c5dcc, #bd9af2 50%, #ffd98a)", description: "一列会唱歌的星星列车穿过云海，带大家寻找勇气宝石。", process: ["写下列车旅行故事", "安排云海和宝石镜头", "挑选明亮又安全的画面"], prompt: "五秒儿童动画：星星列车穿过云海寻找勇气宝石，Q版卡通，温暖明亮。" },
];

export function showcaseProjectById(id: string): ShowcaseProject | undefined {
  return showcaseProjects.find((project) => project.id === id);
}

export const showcaseDefaults = { columns: 4, rows: 2, sort: "热门优先", showStudent: true, requireReview: true } as const;
