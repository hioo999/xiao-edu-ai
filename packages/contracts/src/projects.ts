import type { Id } from "./auth.js";

export type ProjectAssetKind = "text" | "image" | "music" | "video" | "webpage" | "lesson" | "report";

export interface ProjectAssetRef {
  assetId: Id;
  kind: ProjectAssetKind;
  projectId: Id;
}
