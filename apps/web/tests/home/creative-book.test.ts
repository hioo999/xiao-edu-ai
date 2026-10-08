import assert from "node:assert/strict";
import { test } from "node:test";

import { creativeHouses } from "../../src/creative-houses.ts";

test("creative book maps six distinct buildings to student creation routes", () => {
  assert.equal(creativeHouses.length, 6);
  assert.equal(new Set(creativeHouses.map((house) => house.href)).size, 6);
  assert.deepEqual(
    creativeHouses.map((house) => house.id),
    ["chat", "html", "image", "music", "video", "agents"],
  );
});
