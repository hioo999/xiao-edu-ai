import { CreativeWorkspace, type CreativeKind } from "../../components/creative-workspace";

export default async function CreativeWorkspacePage({ params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;
  const supported: CreativeKind[] = ["chat", "image", "music", "video"];
  const selected = supported.includes(kind as CreativeKind) ? (kind as CreativeKind) : "chat";
  return <CreativeWorkspace kind={selected} />;
}
