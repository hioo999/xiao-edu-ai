import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("creative workspace renders completed media previews and download links", () => {
  const source = readFileSync(new URL("../app/components/creative-workspace.tsx", import.meta.url), "utf8");

  assert.match(source, /getWork\(accessToken, job\.assetId\)/);
  assert.match(source, /<img className="studio-media-preview"/);
  assert.match(source, /<video className="studio-media-preview" controls/);
  assert.match(source, /<audio className="studio-audio-preview" controls/);
  assert.match(source, /下载作品/);
});

test("creative workspace uploads a validated reference image before image or video generation", () => {
  const source = readFileSync(new URL("../app/components/creative-workspace.tsx", import.meta.url), "utf8");

  assert.match(source, /uploadReferenceImage/);
  assert.match(source, /referenceImageUrl/);
  assert.match(source, /accept="image\/png,image\/jpeg,image\/webp"/);
  assert.match(source, /上传参考图（必选）/);
  assert.match(source, /videoMode !== "图生视频" \|\| Boolean\(referenceImageUrl\)/);
  assert.doesNotMatch(source, /首尾帧视频/);
});

test("creative workspace provides local voice input and passes image options into generation context", () => {
  const source = readFileSync(new URL("../app/components/creative-workspace.tsx", import.meta.url), "utf8");

  assert.match(source, /SpeechRecognition/);
  assert.match(source, /webkitSpeechRecognition/);
  assert.match(source, /recognition\.lang = "zh-CN"/);
  assert.match(source, /onClick=\{startVoiceInput\}/);
  assert.match(source, /const \[imageRatio, setImageRatio\]/);
  assert.match(source, /const \[imageHint, setImageHint\]/);
  assert.match(source, /\[selectedPreset, imageRatio, imageHint\.trim\(\)\]/);
  assert.doesNotMatch(source, /onSelect=\{\(\) => undefined\}/);
});
