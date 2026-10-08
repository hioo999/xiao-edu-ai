import { playgroundGames } from "../../src/games";

export default function PlaygroundPage() {
  return (
    <main className="game-hub">
      <header className="game-hub__header">
        <a href="/workspace/html" className="game-hub__back">← 回到网页创作</a>
        <a href="/" className="game-hub__brand"><span>✦</span> 星芽 AI 创作岛</a>
        <span className="game-hub__badge">先玩一玩，再创造</span>
      </header>
      <section className="game-hub__hero">
        <div>
          <p>HTML 创作小站 · GAME LAB</p>
          <h1>小游戏试玩乐园</h1>
          <strong>先打开一个游戏，观察它怎么动、怎么得分，再用一句话做出属于你的网页小游戏！</strong>
        </div>
        <div aria-hidden="true" className="game-hub__mascot">🛸<span>🎮</span><i>✨</i></div>
      </section>
      <section aria-label="可试玩小游戏" className="game-gallery">
        {playgroundGames.map((game, index) => (
          <a className={`game-card game-card--${game.color}`} href={`/play/${game.id}`} key={game.id}>
            <span className="game-card__number">{String(index + 1).padStart(2, "0")}</span>
            <span className="game-card__icon" aria-hidden="true">{game.icon}</span>
            <h2>{game.title}</h2>
            <p>{game.description}</p>
            <small>{game.controls}</small>
            <b>开始试玩 <em>→</em></b>
          </a>
        ))}
      </section>
      <aside className="game-hub__tip"><span>💡</span><p><strong>创作灵感：</strong>试玩后可以回到网页创作，告诉 AI：<q>帮我做一个“收集星星”的小游戏网页。</q> 不需要自己写代码。</p><a href="/workspace/html">我要做自己的游戏 →</a></aside>
    </main>
  );
}
