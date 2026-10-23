export type CreativeTextBlock =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string };

function stripInlineMarkdown(value: string): string {
  return value
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/^\s*[-*]\s+/, "")
    .trim();
}

function splitParagraphs(text: string): string[] {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  if (!normalized) return [];
  const blankLineParagraphs = normalized.split(/\n\s*\n/).map((item) => item.trim()).filter(Boolean);
  if (blankLineParagraphs.length > 1) return blankLineParagraphs;
  return normalized.split("\n").map((item) => item.trim()).filter(Boolean);
}

export function parseCreativeText(text: string): CreativeTextBlock[] {
  const blocks: CreativeTextBlock[] = [];
  for (const paragraph of splitParagraphs(text)) {
    const lines = paragraph.split("\n").map((line) => line.trim()).filter(Boolean);
    const heading = lines[0]?.match(/^(#{1,3})\s*(.+)$/);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length as 1 | 2 | 3, text: stripInlineMarkdown(heading[2]) });
      if (lines.length > 1) blocks.push({ kind: "paragraph", text: stripInlineMarkdown(lines.slice(1).join(" ")) });
      continue;
    }
    blocks.push({ kind: "paragraph", text: stripInlineMarkdown(lines.join(" ")) });
  }
  if (!blocks.some((block) => block.kind === "heading")) return blocks;
  return blocks.filter((block) => block.text.length > 0);
}
