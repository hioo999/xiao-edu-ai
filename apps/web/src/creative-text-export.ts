import { parseCreativeText } from "./creative-text-format.ts";

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character] ?? character);
}

export function buildWordDocument(title: string, text: string): string {
  const blocks = parseCreativeText(text);
  const content = blocks.map((block) => {
    if (block.kind === "heading") return `<h${block.level}>${escapeHtml(block.text)}</h${block.level}>`;
    return `<p>${escapeHtml(block.text)}</p>`;
  }).join("");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>body{font-family:'Microsoft YaHei',sans-serif;color:#26364f;line-height:2;padding:36px}h1,h2,h3{text-align:center;font-weight:700;margin:0 0 22px}p{text-indent:2em;margin:12px 0}h1{font-size:24pt}h2{font-size:20pt}h3{font-size:16pt}</style></head><body>${content || `<p>${escapeHtml(text)}</p>`}</body></html>`;
}

export function safeDownloadName(value: string): string {
  const normalized = value.replace(/[\\/:*?"<>|\r\n]+/g, " ").trim();
  return (normalized || "AI创作结果").slice(0, 80);
}
