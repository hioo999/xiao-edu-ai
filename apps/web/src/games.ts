export type PlaygroundGame = {
  id: string;
  title: string;
  icon: string;
  description: string;
  controls: string;
  lesson: string;
  source: string;
  color: string;
};

export const playgroundGames: PlaygroundGame[] = [
  { id: "mario", title: "超级玛丽闯关", icon: "🍄", description: "跳过障碍，收集星星，完成小小冒险。", controls: "方向键移动 · 空格跳跃", lesson: "观察角色移动、碰撞和关卡设计。", source: "/games/mario/index.html", color: "pink" },
  { id: "snake", title: "贪吃蛇", icon: "🐍", description: "吃到更多水果，让小蛇越长越厉害。", controls: "方向键控制方向", lesson: "试试用规则让角色自动做决定。", source: "/games/snake/index.html", color: "mint" },
  { id: "tetris", title: "俄罗斯方块", icon: "🧩", description: "旋转、移动和消除，挑战更高分数。", controls: "方向键 · 空格快速下落", lesson: "体验网格、旋转和消除规则。", source: "/games/tetris/index.html", color: "purple" },
  { id: "tower-defense", title: "塔防守卫", icon: "🏰", description: "摆好防御塔，守护你的奇幻城堡。", controls: "鼠标点击放置和升级", lesson: "学习资源、策略和关卡节奏。", source: "/games/tower-defense/index.html", color: "gold" },
  { id: "sanguo-defense", title: "三国塔防", icon: "⚔️", description: "指挥小将守住阵地，挑战一波波敌人。", controls: "鼠标点击布阵", lesson: "看看不同单位怎样组成团队。", source: "/games/sanguo-defense/index.html", color: "orange" },
  { id: "tank-battle", title: "坦克大战", icon: "🚜", description: "开着坦克躲避攻击，完成热血对战。", controls: "方向键移动 · 空格发射", lesson: "发现移动、发射与胜负规则。", source: "/games/tank-battle/index.html", color: "blue" },
];

export function findPlaygroundGame(id: string) {
  return playgroundGames.find((game) => game.id === id);
}
