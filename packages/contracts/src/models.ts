export type ModelCapability = "text" | "image" | "music" | "video" | "embedding" | "speech_to_text" | "text_to_speech" | "moderation";

export type ModelRegion = "domestic" | "foreign";

export interface ModelDescriptor {
  providerId: string;
  modelName: string;
  capability: ModelCapability;
  region: ModelRegion;
  enabled: boolean;
}
