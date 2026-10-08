export function AuthIllustration() {
  return (
    <section className="auth-illustration" aria-label="星芽 AI 创作岛">
      <div className="auth-illustration__sky" />
      <a className="auth-illustration__brand" href="/">
        <span>✦</span>
        星芽 AI 创作岛
      </a>
      <div className="auth-illustration__copy">
        <p>HELLO, 小小创造家</p>
        <h1>把奇妙想法<br /><em>变成作品！</em></h1>
        <span>说一句话，就能创作网页、图片、音乐和视频。</span>
      </div>
      <img src="/creative-book-world.png" alt="打开的 AI 创作书与创作岛" />
      <div className="auth-illustration__chips" aria-hidden="true">
        <span>✦ 网页</span><span>● 图片</span><span>♫ 音乐</span><span>▶ 视频</span>
      </div>
      <p className="auth-illustration__footer">和 AI 伙伴一起，完成今天的小小创作。</p>
    </section>
  );
}
