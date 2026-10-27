import { CreativeIslandHero } from "./components/creative-island-hero";
import { StudentAccountEntrance } from "./components/student-account-entrance";
import { StudentShowcase } from "./components/student-showcase";

export default function StudentHomePage() {
  return <main className="kids-home"><header className="kids-home__topbar"><a className="kids-brand" href="/"><span aria-hidden="true">✦</span>星芽 AI 创作岛</a><nav aria-label="学生端主导航"><a href="/inspiration">灵感卡</a><a href="/projects">我的作品</a><a href="/courses">我的课程</a></nav><StudentAccountEntrance /></header><section className="kids-hero"><CreativeIslandHero /></section><section className="kids-mission"><div aria-hidden="true">🎒</div><p><strong>今日小任务：给校园小花做一张会说话的海报</strong><span>3 个小步骤 · 预计 15 分钟 · 完成收集一枚星星</span></p><a href="/inspiration">开始任务</a></section><StudentShowcase /></main>;
}
