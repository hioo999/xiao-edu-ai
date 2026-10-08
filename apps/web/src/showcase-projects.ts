export type ShowcaseProjectType = "网页" | "图片" | "音乐" | "视频";

export type ShowcaseProject = {
  id: string;
  title: string;
  student: string;
  type: ShowcaseProjectType;
  cover: string;
  description: string;
  process: string[];
  prompt: string;
  featured?: boolean;
};

export const showcaseProjects: ShowcaseProject[] = [
  { id: "magic-book", title: "会发光的魔法书", student: "小星芽", type: "网页", cover: "linear-gradient(145deg, #7e8df5, #55d7e8 55%, #fff0a8)", description: "点开书页，星星会飞出来讲一个勇敢的小故事。", process: ["想象魔法书里的主角", "告诉 AI 要有点击互动", "预览后调整星星颜色"], prompt: "请帮我制作一本会翻页的魔法书网页，点击书页会飞出星星和一句鼓励的话。", featured: true },
  { id: "forest-castle", title: "云端森林城堡", student: "彩虹队", type: "图片", cover: "linear-gradient(145deg, #7bd1a2, #b8f2d0 52%, #fff0a8)", description: "藏在大树和云朵里的城堡，有会说话的小松鼠。", process: ["选择儿童绘画风格", "加入森林和城堡细节", "调整成明亮的童话色彩"], prompt: "云端森林里的彩虹城堡，会说话的小松鼠守在门口，儿童绘本插画风格。" },
  { id: "forest-song", title: "森林精灵进行曲", student: "音符小组", type: "音乐", cover: "linear-gradient(145deg, #a98bf4, #ffb8d0 52%, #ffe18a)", description: "一首和小伙伴一起走进森林的快乐儿歌。", process: ["写下森林探险主题", "选择轻快节奏", "试听并修改副歌"], prompt: "创作一首关于森林精灵和好朋友探险的快乐儿童歌曲，副歌要简单好唱。" },
  { id: "magic-brush", title: "马良的神笔", student: "小画家", type: "视频", cover: "linear-gradient(145deg, #ffaf91, #ffd36e 52%, #8fbdff)", description: "神笔画出一条小龙，小龙飞过校园送来彩虹。", process: ["把故事分成三个镜头", "描述主角和动作", "生成后挑选最喜欢的一段"], prompt: "神笔画出一条可爱的小龙，小龙飞过校园，在天空留下彩虹，明亮卡通短片。" },
];

export const showcaseDefaults = { columns: 4, rows: 2, sort: "精选优先", showStudent: true, requireReview: true } as const;
