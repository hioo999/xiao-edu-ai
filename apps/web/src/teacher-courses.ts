export type TeacherCourse = {
  id: string;
  title: string;
  grade: string;
  lessons: number;
  status: string;
  updated: string;
  transcript: string[];
  prompts: string[];
  flow: string[];
};

export const teacherCourses: TeacherCourse[] = [
  {
    id: "first-webpage",
    title: "我的第一个网页",
    grade: "四年级",
    lessons: 6,
    status: "已发布",
    updated: "今天 14:20",
    transcript: ["大家先想一想：你希望别人打开网页时第一眼看到什么？", "现在告诉网页老师你的主题、颜色和想放进去的按钮。", "生成后不要急着结束，我们一起检查文字、布局和按钮是否清楚。"],
    prompts: ["请制作一个适合小学生的互动网页，主题是校园植物观察。", "请把标题改得更有童趣，并增加一个‘开始探索’按钮。", "请用明亮的绿色和黄色，让页面看起来像春天的花园。"],
    flow: ["认识网页的组成", "用自然语言描述网页", "和 AI 一起修改页面", "预览网页并下载作品"],
  },
  {
    id: "ai-introduction",
    title: "欢迎认识 AI",
    grade: "三年级",
    lessons: 4,
    status: "草稿",
    updated: "昨天 16:10",
    transcript: ["AI 像一个会学习的伙伴，但我们仍然要负责提出好问题。", "请观察 AI 的回答，找一找哪些地方需要补充或检查。"],
    prompts: ["请用小学生能听懂的话解释什么是人工智能。", "请给我设计一个认识 AI 的小游戏。"],
    flow: ["认识 AI 伙伴", "学会提出问题", "检查 AI 的回答", "完成认识 AI 小挑战"],
  },
];

export const defaultCourseUploadTypes = ["PDF 课件", "PPTX 课件", "DOCX 教案", "MP4 课堂视频", "PNG / JPG 图片"];
