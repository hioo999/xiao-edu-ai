import assert from "node:assert/strict";
import { test } from "node:test";
import { buildMusicLyricsPrompt, requireGeneratedLyrics } from "../src/music-creation.ts";

test("music lyrics prompt asks for a song rather than a follow-up question", () => {
  const prompt = buildMusicLyricsPrompt("星星歌", "和朋友一起看星空");
  assert.match(prompt, /星星歌/);
  assert.match(prompt, /和朋友一起看星空/);
  assert.match(prompt, /只输出歌词正文/);
  assert.match(prompt, /不要提问/);
});

test("blank model output never becomes a paid music task", () => {
  assert.throws(() => requireGeneratedLyrics("  \n"), /歌曲尚未提交/);
  assert.equal(requireGeneratedLyrics("主歌\n副歌\n"), "主歌\n副歌");
});
