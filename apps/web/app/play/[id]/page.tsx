import { notFound } from "next/navigation";

import { findPlaygroundGame } from "../../../src/games";

export default async function GamePlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const game = findPlaygroundGame(id);
  if (!game) notFound();

  return (
    <main className="game-player">
      <header className="game-player__header">
        <a href="/play">← 返回小游戏乐园</a>
        <div><span>{game.icon}</span><strong>{game.title}</strong><small>{game.controls}</small></div>
        <a className="game-player__create" href={`/workspace/html?prompt=${encodeURIComponent(`参考${game.title}的玩法，帮我制作一个适合小学生的小游戏网页`)}`}>用这个灵感创作网页 →</a>
      </header>
      <section className="game-player__frame-wrap" aria-label={`${game.title}游戏区域`}>
        <iframe className="game-player__frame" title={`${game.title}小游戏试玩`} src={game.source} sandbox="allow-scripts allow-pointer-lock" />
      </section>
      <footer className="game-player__footer"><span>💡</span><p><strong>玩完想一想：</strong>{game.lesson}</p><a href="/workspace/html">去网页创作</a></footer>
    </main>
  );
}
