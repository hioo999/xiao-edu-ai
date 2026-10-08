import { test } from "node:test";
import assert from "node:assert/strict";

import { canEnterFeature, getVisibleFeatures } from "../../src/student-shell.ts";

test("student shell exposes multimodal creative entrances", () => {
  const features = getVisibleFeatures();

  assert.deepEqual(
    features.map((feature) => feature.id),
    ["chat", "html", "image", "music", "video", "expert-team", "courses", "projects"],
  );
});

test("disabled feature cannot be entered", () => {
  const features = getVisibleFeatures().map((feature) =>
    feature.id === "video" ? { ...feature, enabled: false } : feature,
  );

  assert.equal(canEnterFeature("video", features), false);
  assert.equal(canEnterFeature("html", features), true);
});
