import { parseCreativeText } from "../../src/creative-text-format";

export function FormattedCreativeText({ text }: { text: string }) {
  const blocks = parseCreativeText(text);
  return <div className="formatted-creative-text">
    {blocks.map((block, index) => {
      if (block.kind === "heading") {
        const Tag = block.level === 1 ? "h1" : block.level === 2 ? "h2" : "h3";
        return <Tag key={`${block.kind}-${index}`}>{block.text}</Tag>;
      }
      return <p key={`${block.kind}-${index}`}>{block.text}</p>;
    })}
  </div>;
}
