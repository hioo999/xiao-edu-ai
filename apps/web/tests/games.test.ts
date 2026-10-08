import assert from "node:assert/strict";
import { test } from "node:test";

import { findPlaygroundGame, playgroundGames } from "../src/games.ts";

test("game playground exposes six locally hosted student games", () => {
  assert.equal(playgroundGames.length, 6);
  assert.equal(new Set(playgroundGames.map((game) => game.id)).size, playgroundGames.length);
  for (const game of playgroundGames) {
    assert.match(game.source, /^\/games\/[a-z-]+\/index\.html$/);
    assert.ok(game.controls.length > 0);
    assert.ok(game.lesson.length > 0);
  }
});

test("game lookup returns a matching game and handles unknown routes", () => {
  assert.equal(findPlaygroundGame("snake")?.title, "贪吃蛇");
  assert.equal(findPlaygroundGame("not-a-game"), undefined);
});
