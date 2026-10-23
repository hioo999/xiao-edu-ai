export function buildMusicLyricsPrompt(title: string, theme: string): string {
  return `你是小学三至六年级的儿童歌曲作词人。请根据歌曲《${title.trim()}》的主题“${theme.trim()}”创作适合儿童演唱的原创中文歌词。只输出歌词正文，包含简短的主歌和副歌；语言积极、易懂，不要提问、解释、Markdown 标题或代码块。`;
}

export function requireGeneratedLyrics(content: string): string {
  const lyrics = content.trim();
  if (!lyrics) throw new Error("歌词生成失败，请稍后重试，歌曲尚未提交。");
  return lyrics;
}
